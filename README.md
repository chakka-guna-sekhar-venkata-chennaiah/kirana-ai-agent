# KiranaAI — Text2Cypher + Text2SQL Agentic AI for Indian Kirana Stores

> Neo4j GraphAcademy Cup Submission | Country: India
> Courses: Cypher Fundamentals · Neo4j Fundamentals

---

## What is KiranaAI?

KiranaAI is a conversational AI agent for a Telugu kirana (grocery) store owner. The owner asks questions in **Tenglish** (Telugu + English, Roman script) and gets instant answers — without writing a single query.

The agent intelligently decides which database to use based on intent:

| Question type | Tool | Example |
|---|---|---|
| Relationships, co-buys, credit | **Neo4j** (Text2Cypher) | "Atta tho paatu em adugutaaru?" |
| Stock, sales, billing | **SQLite** (Text2SQL) | "Naadu inka em stock undi?" |
| Trend charts | **Plotly** | "Category wise sales chupinchu" |

---

## Why Neo4j for a Kirana Store?

A kirana store's richest insights live in **relationships** — which SQL JOINs cannot express naturally:

```
(Customer)-[:PURCHASED {times}]->(Product)
(Customer)-[:OWES]->(Khata {balance})
(Product)-[:OFTEN_WITH {strength}]->(Product)
(Product)-[:SUPPLIED_BY]->(Supplier)
(Customer)-[:REFERRED_BY]->(Customer)
```

- **"Atta ke saath kya suggest karein?"** → traverses `OFTEN_WITH` in one hop
- **"Evaru evaru udhar teeyaali?"** → traverses `Customer → OWES → Khata`
- **"Basmati Rice ekkadi nundi vastaundi?"** → traverses `Product → SUPPLIED_BY → Supplier`

Text2Cypher translates these natural language questions to Cypher automatically — no Cypher knowledge required.

---

## Architecture

```
Owner Question (Tenglish)
         │
         ▼
  DeepSeek LLM (LangGraph ReAct Agent)
         │
   ┌─────┴────────────────┐
   │                      │
neo4j_search          sql_query
(Text2Cypher          (Text2SQL
 → Neo4j Aura)         → SQLite)
   │                      │
   └──────────┬───────────┘
              │
     create_visualization
          (Plotly)
              │
              ▼
   Answer in Tenglish
   + Interactive Graph (pyvis)
   + Chart (when numeric)
```

---

## Tech Stack

| Component | Technology |
|---|---|
| LLM | DeepSeek Chat API |
| Agent | LangGraph `create_react_agent` (ReAct pattern) |
| Text2Cypher | `GraphCypherQAChain` from `langchain-neo4j` |
| Graph DB | Neo4j Aura (cloud) |
| Relational DB | SQLite |
| UI | Streamlit (streaming agent thoughts) |
| Graph viz | pyvis (interactive force-directed) |
| Charts | Plotly Express |

---

## Quick Start

### 1. Clone & install
```bash
git clone https://github.com/YOUR_USERNAME/kirana-ai-agent
cd kirana-ai-agent
pip install -r requirements.txt
```

### 2. Configure
```bash
cp .env.example .env
# Edit .env — add DEEPSEEK_API_KEY and Neo4j Aura credentials
```

### 3. Seed databases
```bash
python database/sqlite_setup.py
python database/neo4j_setup.py
```

### 4. Run
```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) and start asking in Tenglish!

---

## Project Structure

```
kirana-ai-agent/
├── app.py                    # Streamlit chat UI
├── requirements.txt
├── .env.example
├── agent/
│   ├── agent.py              # LangGraph ReAct agent builder
│   ├── tools.py              # sql_query, neo4j_search, create_visualization
│   ├── prompts.py            # System prompt (Tenglish persona)
│   └── few_shots.py          # Verified Cypher examples for Text2Cypher
└── database/
    ├── sqlite_setup.py       # SQLite schema + 30-day seed data
    └── neo4j_setup.py        # Neo4j nodes + relationships seed
```

---

## Sample Queries

```
Owner: "Evaru evaru udhar teeyaali?"
AI:    "Mohan Lal gaaru Rs.450 teeyaali — maximum undi.
        Ramesh Kumar Rs.250, Vijay Singh Rs.180, Suresh Yadav Rs.120.
        Total udhar: Rs.1,000."

Owner: "Atta tho paatu em adugutaaru customers?"
AI:    "Atta konne vaallaki Toor Dal (strength 20) mariyu Sugar (strength 15)
        suggest cheyyi — chala mandi saath kontaaru!"

Owner: "Ee vaaram total sale enta aindi?"
AI:    "Ee vaaram Rs.14,850 sale aindi. [chart below]"
```

---

*Built for India's 12 million kirana store owners — making AI accessible without technical knowledge.*
