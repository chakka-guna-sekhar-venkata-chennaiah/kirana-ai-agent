"""
KiranaAI Tools — LangChain tools exposed to the ReAct agent.

  sql_query        → SQLite (structured / transactional data)
  neo4j_search     → Neo4j graph via Text2Cypher (relationships / patterns)
  create_visualization → Plotly chart from either tool's output
"""
import json
import os
import sqlite3
from typing import Optional

import pandas as pd
import plotly.express as px
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool
from langchain_neo4j import GraphCypherQAChain, Neo4jGraph
from neo4j import GraphDatabase
from neo4j.graph import Node, Relationship

load_dotenv()

SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "kirana_store.db")
NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USERNAME", os.getenv("NEO4J_USER", "neo4j"))
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

CHART_PALETTE = ["#2a78d6", "#1baf7a", "#eda100", "#4a3aa7", "#e34948"]


def _build_cypher_prompt() -> PromptTemplate:
    """
    Build the Cypher generation prompt with verified few-shot examples injected.
    Few-shots anchor the LLM to simple, tested queries and prevent it from
    inventing complex aggregations that don't match the graph structure.
    """
    from agent.few_shots import FEW_SHOT_EXAMPLES
    examples_block = "\n\n".join(
        f"Question: {ex['question']}\nCypher: {ex['cypher']}"
        for ex in FEW_SHOT_EXAMPLES
    )
    # Cypher property maps use {key: value} syntax which PromptTemplate mistakes for
    # template variables. Double-brace them so they pass through as literal text.
    examples_safe = examples_block.replace("{", "{{").replace("}", "}}")
    return PromptTemplate(
        input_variables=["schema", "question"],
        template=f"""You are a Neo4j Cypher expert for a kirana (Indian grocery) store graph database.

Graph schema:
{{schema}}

Verified examples — follow these patterns closely:

{examples_safe}

Rules:
- Use ONLY node labels and relationship types defined in the schema above.
- Generate READ-only queries (MATCH/RETURN). Never write MERGE, CREATE, SET, or DELETE.
- ALWAYS return full node and relationship variables (e.g. RETURN c, r, p), never scalars.
- Keep queries SIMPLE — no WITH blocks, no aggregations, no computed properties.
  Totals, counts, and sums belong in SQL, not in graph queries.
- Add LIMIT 25 unless the question explicitly asks for all data.
- Output ONLY the Cypher statement — no explanation, no markdown fences.

Question: {{question}}
Cypher:""",
    )


def _build_llm():
    from langchain_openai import ChatOpenAI
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY is not set in the environment.")
    return ChatOpenAI(
        model="deepseek-chat",
        api_key=api_key,
        base_url="https://api.deepseek.com/v1",
        temperature=0,
    )


def _extract_graph_data(raw_records: list) -> tuple[dict, list]:
    """
    Walk neo4j driver records and separate Node/Relationship objects (for graph
    rendering) from scalar values (for LLM reasoning).

    Returns (graph_nodes_dict keyed by element_id, graph_edges list).
    """
    graph_nodes: dict = {}
    graph_edges: list = []

    def _add_node(n: Node) -> None:
        eid = n.element_id
        if eid not in graph_nodes:
            graph_nodes[eid] = {
                "id":         eid,
                "labels":     list(n.labels),
                "properties": dict(n),
            }

    for rec in raw_records:
        for val in rec.values():
            if isinstance(val, Node):
                _add_node(val)
            elif isinstance(val, Relationship):
                # Always capture both endpoints, even if they are anonymous
                # in the RETURN clause — otherwise edges reference missing nodes.
                _add_node(val.start_node)
                _add_node(val.end_node)
                graph_edges.append({
                    "source":     val.start_node.element_id,
                    "target":     val.end_node.element_id,
                    "type":       val.type,
                    "properties": dict(val),
                })

    return graph_nodes, graph_edges


# ── Tool 1: SQL ────────────────────────────────────────────────────────────────

@tool
def sql_query(query: str) -> str:
    """
    Execute a read-only SQL SELECT on the kirana store's SQLite database.

    Use for: stock levels, sales totals, transaction history, billing,
    product prices, category summaries, low-stock alerts, payment modes.

    Tables:
      products          (id, name, category, price, stock_quantity, unit, min_stock, supplier_id)
      customers         (id, name, phone, address, registered_date)
      transactions      (id, customer_id, date, total_amount, payment_mode, is_credit)
      transaction_items (id, transaction_id, product_id, quantity, unit_price)
      credit_accounts   (id, customer_id, balance, credit_limit)
      suppliers         (id, name, contact, category)

    Only SELECT statements are permitted. Returns a JSON array of rows (max 50).
    """
    if not query.strip().upper().startswith("SELECT"):
        return json.dumps({"error": "Only SELECT queries are permitted."})

    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(query)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

        if not rows:
            return json.dumps({"message": "No records found."})
        return json.dumps(rows[:50], ensure_ascii=False, default=str)

    except sqlite3.Error as e:
        return json.dumps({"error": str(e), "query": query})


# ── Tool 2: Neo4j Text2Cypher ─────────────────────────────────────────────────

@tool
def neo4j_search(question: str) -> str:
    """
    Search the Neo4j graph database using natural language (Text2Cypher).

    Use for: customer relationships, purchase patterns, khata/udhar (credit balances),
    product co-buys and recommendations (OFTEN_WITH), supplier chains,
    referral networks, loyalty analysis.

    When the answer involves connections or networks, the UI will automatically
    render an interactive graph in addition to the text answer.
    """
    try:
        graph = Neo4jGraph(
            url=NEO4J_URI,
            username=NEO4J_USER,
            password=NEO4J_PASSWORD,
            database=NEO4J_DATABASE,
            enhanced_schema=True,  # sends property examples to help LLM avoid wrong types
        )

        chain = GraphCypherQAChain.from_llm(
            llm=_build_llm(),
            graph=graph,
            cypher_prompt=_build_cypher_prompt(),
            return_intermediate_steps=True,
            allow_dangerous_requests=True,
            verbose=False,
        )

        result = chain.invoke({"query": question})
        text_answer    = result.get("result", "")
        steps          = result.get("intermediate_steps") or [{}]
        generated_cypher = steps[0].get("query", "").strip()

        # Re-run with raw driver to capture Node/Relationship objects for graph viz
        graph_nodes: dict = {}
        graph_edges: list = []
        tabular: list     = []

        if generated_cypher:
            driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            try:
                with driver.session(database=NEO4J_DATABASE) as session:
                    raw_records = list(session.run(generated_cypher))

                graph_nodes, graph_edges = _extract_graph_data(raw_records)

                for rec in raw_records:
                    row = {}
                    for key, val in rec.items():
                        if isinstance(val, Node):
                            row[key] = dict(val)
                        elif isinstance(val, Relationship):
                            row[key] = {"type": val.type, **dict(val)}
                        else:
                            row[key] = val
                    tabular.append(row)
            finally:
                driver.close()

        payload: dict = {
            "answer":           text_answer,
            "records":          tabular[:20],
            "cypher_generated": generated_cypher,
        }
        if graph_nodes:
            payload["__graph__"] = {
                "nodes": list(graph_nodes.values()),
                "edges": graph_edges,
            }

        return json.dumps(payload, ensure_ascii=False, default=str)

    except Exception as e:
        return json.dumps({"error": str(e)})


# ── Tool 3: Visualization ──────────────────────────────────────────────────────

@tool
def create_visualization(
    data_json: str,
    chart_type: str,
    title: str,
    x_col: Optional[str] = None,
    y_col: Optional[str] = None,
) -> str:
    """
    Create a Plotly chart from the output of sql_query or neo4j_search.
    Call this when results contain numeric data worth visualising.

    Args:
        data_json  : JSON string — exact output from sql_query or neo4j_search.
        chart_type : 'bar' | 'horizontal_bar' | 'line' | 'pie'
        title      : Plain-language chart title (e.g. "Weekly Sales by Category")
        x_col      : Column for the X-axis / category (auto-detected if omitted)
        y_col      : Column for the Y-axis / values   (auto-detected if omitted)

    Returns a special token {"type":"plotly","figure":"..."} that the UI renders.
    """
    try:
        raw = json.loads(data_json)

        # Normalise: accept list, neo4j_search dict, or sql_query dict
        if isinstance(raw, list):
            records = raw
        elif isinstance(raw, dict):
            if raw.get("type") == "plotly":
                return json.dumps({"error": "Input is already a chart."})
            if "message" in raw:
                return json.dumps({"error": raw["message"]})
            if "error" in raw:
                return json.dumps({"error": raw["error"]})
            # neo4j_search returns {"answer":..., "records":[...], ...}
            records = raw.get("records") or [raw]
        else:
            return json.dumps({"error": "Unrecognised data format."})

        # Flatten any residual nested dicts (e.g. neo4j node blobs)
        flat_records = []
        for r in records:
            flat = {k: (str(v) if isinstance(v, (dict, list)) else v) for k, v in r.items()}
            flat_records.append(flat)

        df = pd.DataFrame(flat_records)
        if df.empty:
            return json.dumps({"error": "No data to chart."})

        num_cols = df.select_dtypes(include="number").columns.tolist()
        str_cols = df.select_dtypes(exclude="number").columns.tolist()

        x = x_col or (str_cols[0] if str_cols else df.columns[0])
        y = y_col or (num_cols[0] if num_cols else df.columns[-1])

        common = dict(color_discrete_sequence=CHART_PALETTE)

        if chart_type == "horizontal_bar":
            fig = px.bar(df, x=y, y=x, orientation="h", title=title, text_auto=True, **common)
        elif chart_type == "line":
            fig = px.line(df, x=x, y=y, title=title, markers=True, **common)
        elif chart_type == "pie":
            fig = px.pie(df, names=x, values=y, title=title, **common)
        else:
            fig = px.bar(df, x=x, y=y, title=title, text_auto=True, **common)

        fig.update_layout(
            template="plotly_white",
            margin=dict(t=50, l=20, r=20, b=20),
            font_family="sans-serif",
            title_font_size=15,
        )

        return json.dumps({"type": "plotly", "figure": fig.to_json()})

    except Exception as e:
        return json.dumps({"error": f"Visualization failed: {e}"})
