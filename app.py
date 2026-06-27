"""
KiranaAI — Streamlit Chat Interface
Streams LangGraph ReAct agent thoughts and renders Plotly charts and Neo4j graphs inline.
"""
import json
import os
import sqlite3
import tempfile

import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from pyvis.network import Network

load_dotenv()

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="KiranaAI",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.main-header {
    background: linear-gradient(135deg, #FF6B35 0%, #e85d2f 100%);
    padding: 16px 24px;
    border-radius: 10px;
    color: white;
    margin-bottom: 1rem;
}
.main-header h1 { margin: 0; font-size: 1.5rem; font-weight: 700; }
.main-header p  { margin: 4px 0 0; font-size: 0.85rem; opacity: 0.88; }
.tool-tag {
    display: inline-block;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 10px;
    margin: 2px 0;
}
.tag-sql   { background:#E6F1FB; color:#185FA5; }
.tag-neo4j { background:#E1F5EE; color:#0F6E56; }
.tag-viz   { background:#FAEEDA; color:#854F0B; }
</style>
""", unsafe_allow_html=True)


# ── Database health checks ─────────────────────────────────────────────────────

def check_sqlite() -> tuple[bool, str]:
    db = os.getenv("SQLITE_DB_PATH", "kirana_store.db")
    if not os.path.exists(db):
        return False, "file not found"
    try:
        conn = sqlite3.connect(db)
        cnt  = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        conn.close()
        return True, f"{cnt} products"
    except Exception as e:
        return False, str(e)


def check_neo4j() -> tuple[bool, str]:
    try:
        from neo4j import GraphDatabase
        uri  = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USERNAME", os.getenv("NEO4J_USER", "neo4j"))
        pwd  = os.getenv("NEO4J_PASSWORD", "")
        db   = os.getenv("NEO4J_DATABASE", "neo4j")
        driver = GraphDatabase.driver(uri, auth=(user, pwd))
        with driver.session(database=db) as s:
            cnt = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        driver.close()
        return True, f"{cnt} nodes"
    except Exception as e:
        return False, str(e)


# ── Constants ──────────────────────────────────────────────────────────────────

TOOL_META = {
    "sql_query":            ("🗄️", "SQL",         "tag-sql"),
    "neo4j_search":         ("🔗", "Neo4j",        "tag-neo4j"),
    "create_visualization": ("📊", "Visualization", "tag-viz"),
}

SAMPLE_QUESTIONS = [
    # Neo4j-led questions that naturally pull SQL data too
    "Regular ga vaache customers evaru, valla total spend enta?",
    "Udhar lo unna customers recently em konnaru?",
    "Atta konne customers ki em suggest cheyaali, aa items stock lo unnaya?",
    "Evaru evaru udhar teeyaali, enta baaki undi?",
    "Basmati Rice ekkadi nundi vastaundi, inka stock enta undi?",
    "Most loyal customers evaru, valla total purchase enta?",
    # Primarily SQL
    "Naadu inka em stock undi?",
    "Ee vaaram total sale enta aindi?",
    "Em items aipothunnaayi — restock cheyaali?",
    "Category wise sales chupinchu",
]

NODE_COLORS = {
    "Customer": "#2a78d6",
    "Product":  "#1baf7a",
    "Supplier": "#eda100",
    "Khata":    "#e34948",
}
NODE_SIZES = {
    "Customer": 28,
    "Product":  22,
    "Supplier": 26,
    "Khata":    20,
}


# ── Graph renderer ─────────────────────────────────────────────────────────────

def render_neo4j_graph(graph_data: dict, height: int = 540) -> None:
    """Render Neo4j nodes + relationships as an interactive force-directed graph."""
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    if not nodes:
        st.info("No graph data to display.")
        return

    net = Network(
        height=f"{height}px",
        width="100%",
        bgcolor="#0d1117",
        font_color="#ffffff",
        directed=True,
        notebook=False,
    )

    # Neo4j Browser-like physics: compact, stable, not too spread
    net.set_options(json.dumps({
        "physics": {
            "stabilization": {"iterations": 200, "updateInterval": 10},
            "barnesHut": {
                "gravitationalConstant": -4500,
                "centralGravity": 0.4,
                "springLength": 120,
                "springConstant": 0.04,
                "damping": 0.5,
                "avoidOverlap": 0.6,
            },
        },
        "nodes": {
            "shape": "dot",
            "borderWidth": 2,
            "shadow": {"enabled": True, "size": 6, "color": "rgba(0,0,0,0.4)"},
            "font": {"size": 13, "color": "#ffffff", "bold": True},
        },
        "edges": {
            "width": 2,
            "selectionWidth": 3,
            "color": {"inherit": False, "color": "#6b7280", "highlight": "#ffffff"},
            "font": {"size": 11, "color": "#d1d5db",
                     "background": "#1f2937", "strokeWidth": 0,
                     "align": "middle"},
            "smooth": {"type": "dynamic"},
        },
        "interaction": {
            "hover": True,
            "tooltipDelay": 80,
            "zoomView": True,
            "dragView": True,
            "navigationButtons": True,
        },
    }))

    for node in nodes:
        label  = node["labels"][0] if node.get("labels") else "Node"
        props  = node.get("properties", {})
        color  = NODE_COLORS.get(label, "#6b7280")
        size   = NODE_SIZES.get(label, 22)

        if props.get("name"):
            display = props["name"]
        elif props.get("balance") is not None:
            display = f"₹{props['balance']}"
        else:
            display = str(props.get("id", node["id"]))

        tooltip = (
            f"<b style='color:{color}'>{label}</b><br>"
            + "<br>".join(f"<b>{k}</b>: {v}" for k, v in props.items())
        )

        net.add_node(
            node["id"],
            label=str(display),
            title=tooltip,
            color={
                "background": color,
                "border": "#ffffff",
                "highlight": {"background": color, "border": "#ffffff"},
                "hover":      {"background": color, "border": "#ffffff"},
            },
            size=size,
            font={"size": 13, "color": "#ffffff", "bold": True},
            borderWidth=2,
        )

    node_ids = {n["id"] for n in nodes}
    for edge in edges:
        # Skip edges whose endpoints weren't captured (shouldn't happen after tool fix)
        if edge["source"] not in node_ids or edge["target"] not in node_ids:
            continue

        props   = edge.get("properties", {})
        e_label = edge["type"]
        if "strength" in props:
            e_label += f" ({props['strength']})"
        elif "times" in props:
            e_label += f" x{props['times']}"
        elif "balance" in props:
            e_label += f" Rs.{props['balance']}"

        net.add_edge(
            edge["source"],
            edge["target"],
            label=e_label,
            title=e_label,
            arrows={"to": {"enabled": True, "scaleFactor": 0.5}},
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w") as f:
        net.save_graph(f.name)
        html_content = open(f.name, encoding="utf-8").read()

    components.html(html_content, height=height + 20, scrolling=False)


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🏪 KiranaAI")
    st.markdown("**Database Status**")

    sql_ok, sql_msg = check_sqlite()
    neo_ok, neo_msg = check_neo4j()

    if sql_ok:
        st.success(f"SQLite — {sql_msg}")
    else:
        st.error(f"SQLite — {sql_msg}")

    if neo_ok:
        st.success(f"Neo4j — {neo_msg}")
    else:
        st.error(f"Neo4j — {neo_msg}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Setup DBs", use_container_width=True):
            with st.spinner("Setting up…"):
                from database.sqlite_setup import setup_sqlite
                setup_sqlite()
                if neo_ok:
                    from database.neo4j_setup import setup_neo4j
                    setup_neo4j()
                else:
                    st.warning("Neo4j not reachable — skipped.")
            st.success("Done! Refresh the page.")
    with col2:
        if st.button("Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    st.markdown("---")
    st.markdown("**Try asking:**")
    for q in SAMPLE_QUESTIONS:
        if st.button(q, use_container_width=True, key=f"sq_{q}"):
            st.session_state["auto_input"] = q

    st.markdown("---")
    st.markdown("**How it works**")
    st.code(
        "Natural language query\n"
        "  → DeepSeek LLM (reasoning)\n"
        "     → sql_query    (inventory/sales)\n"
        "     → neo4j_search (Text2Cypher)\n"
        "     → visualization (charts)\n"
        "  → Answer in Hinglish",
        language="text",
    )


# ── Main header ────────────────────────────────────────────────────────────────

st.markdown("""
<div class="main-header">
  <h1>🏪 KiranaAI — Mee Dukaanam AI Nestam</h1>
  <p>Em adugaalanna adugandi — Telugu, English, ledhaa Tenglish lo</p>
</div>
""", unsafe_allow_html=True)


# ── Session state ──────────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []


# ── Render chat history ────────────────────────────────────────────────────────

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("type") == "plotly":
            try:
                st.plotly_chart(go.Figure(json.loads(msg["content"])),
                                use_container_width=True)
            except Exception:
                st.markdown(msg["content"])
        elif msg.get("type") == "graph":
            try:
                st.markdown("**Graph view**")
                render_neo4j_graph(json.loads(msg["content"]))
            except Exception:
                st.markdown("_(graph unavailable)_")
        else:
            st.markdown(msg["content"])


# ── Agent execution ────────────────────────────────────────────────────────────

def run_agent(user_prompt: str) -> None:
    from agent.agent import get_agent

    agent = get_agent()

    with st.chat_message("assistant"):
        with st.expander("Agent thinking…", expanded=False):
            thought_area = st.empty()

        answer_area  = st.empty()
        charts:  list = []
        graphs:  list = []
        thoughts: list = []
        final_answer  = ""

        try:
            for chunk in agent.stream(
                {"messages": [HumanMessage(content=user_prompt)]},
                stream_mode="updates",
            ):
                # Agent node: tool calls or final text
                if "agent" in chunk:
                    for msg in chunk["agent"]["messages"]:
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tc in msg.tool_calls:
                                tname = tc.get("name", "unknown")
                                args  = tc.get("args", {})
                                emoji, label, css = TOOL_META.get(
                                    tname, ("🔧", tname, "tag-sql")
                                )
                                block = (
                                    f'<span class="tool-tag {css}">'
                                    f'{emoji} {label}</span>\n\n'
                                )
                                if tname == "sql_query":
                                    block += f"```sql\n{args.get('query', '')}\n```"
                                elif tname == "neo4j_search":
                                    block += f"**Graph search:** _{args.get('question', '')}_"
                                else:
                                    block += (
                                        f"Chart `{args.get('chart_type', '')}` — "
                                        f"_{args.get('title', '')}_"
                                    )
                                thoughts.append(block)
                                thought_area.markdown(
                                    "\n\n---\n\n".join(thoughts),
                                    unsafe_allow_html=True,
                                )

                        elif hasattr(msg, "content") and msg.content:
                            final_answer = msg.content
                            answer_area.markdown(final_answer)

                # Tools node: results
                elif "tools" in chunk:
                    for msg in chunk["tools"]["messages"]:
                        raw = getattr(msg, "content", str(msg))
                        try:
                            parsed = json.loads(raw)

                            if parsed.get("type") == "plotly":
                                charts.append(parsed["figure"])
                                thoughts.append("Chart created.")

                            elif "__graph__" in parsed:
                                graphs.append(parsed["__graph__"])
                                n = len(parsed["__graph__"]["nodes"])
                                e = len(parsed["__graph__"]["edges"])
                                block = f"Graph: **{n} nodes**, **{e} relationships**"
                                if parsed.get("cypher_generated"):
                                    block += (
                                        f"\n\n```cypher\n"
                                        f"{parsed['cypher_generated']}\n```"
                                    )
                                thoughts.append(block)

                            elif "error" in parsed:
                                thoughts.append(f"Tool error: {parsed['error']}")

                            elif "answer" in parsed:
                                # neo4j_search result without graph data
                                block = ""
                                if parsed.get("cypher_generated"):
                                    block += (
                                        f"```cypher\n"
                                        f"{parsed['cypher_generated']}\n```\n\n"
                                    )
                                block += f"Result: {parsed['answer'][:300]}"
                                thoughts.append(block)

                            else:
                                preview = raw[:300] + ("…" if len(raw) > 300 else "")
                                thoughts.append(
                                    f"Result preview:\n```\n{preview}\n```"
                                )

                        except (json.JSONDecodeError, AttributeError):
                            thoughts.append(
                                f"Result:\n```\n{raw[:300]}\n```"
                            )

                        thought_area.markdown(
                            "\n\n---\n\n".join(thoughts),
                            unsafe_allow_html=True,
                        )

        except Exception as e:
            final_answer = (
                f"Agent error: {e}\n\n"
                "Please check your API key and database connections."
            )
            answer_area.error(final_answer)

        if final_answer:
            st.session_state.messages.append(
                {"role": "assistant", "content": final_answer}
            )

        for g in graphs:
            st.markdown("**Graph view**")
            render_neo4j_graph(g)
            st.session_state.messages.append(
                {"role": "assistant", "type": "graph", "content": json.dumps(g)}
            )

        for fig_json in charts:
            try:
                fig = go.Figure(json.loads(fig_json))
                st.plotly_chart(fig, use_container_width=True)
                st.session_state.messages.append(
                    {"role": "assistant", "type": "plotly", "content": fig_json}
                )
            except Exception as e:
                st.warning(f"Chart render failed: {e}")


# ── Input ──────────────────────────────────────────────────────────────────────

auto       = st.session_state.pop("auto_input", None)
user_input = st.chat_input("Em adugutaaru? (Ask anything about your kirana store)")
prompt     = auto or user_input

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    run_agent(prompt)
