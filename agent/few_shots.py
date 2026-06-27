"""
Verified few-shot examples for Text2Cypher.

Each entry maps a plain-language question to a tested Cypher query that works
against the kirana store graph schema. The LLM uses these as anchors so it
generates simple, reliable queries instead of inventing complex aggregations.

Rule of thumb encoded here: Neo4j handles RELATIONSHIPS, SQL handles AGGREGATIONS.
"""

FEW_SHOT_EXAMPLES = [
    # ── Khata / Udhar ──────────────────────────────────────────────────────
    {
        "question": "Who owes money? Show udhar balances.",
        "cypher": (
            "MATCH (c:Customer)-[r:OWES]->(k:Khata) "
            "RETURN c, r, k "
            "ORDER BY k.balance DESC"
        ),
    },
    {
        "question": "Which customer has the highest udhar?",
        "cypher": (
            "MATCH (c:Customer)-[r:OWES]->(k:Khata) "
            "RETURN c, r, k "
            "ORDER BY k.balance DESC "
            "LIMIT 5"
        ),
    },

    # ── Purchase patterns ──────────────────────────────────────────────────
    {
        "question": "Show customer purchase relationships.",
        "cypher": (
            "MATCH (c:Customer)-[r:PURCHASED]->(p:Product) "
            "RETURN c, r, p "
            "ORDER BY r.times DESC "
            "LIMIT 25"
        ),
    },
    {
        "question": "Which customers are regular or loyal?",
        "cypher": (
            "MATCH (c:Customer)-[r:PURCHASED]->(p:Product) "
            "RETURN c, r, p "
            "ORDER BY r.times DESC "
            "LIMIT 25"
        ),
    },
    {
        "question": "What has Ramesh Kumar purchased?",
        "cypher": (
            "MATCH (c:Customer {name: 'Ramesh Kumar'})-[r:PURCHASED]->(p:Product) "
            "RETURN c, r, p"
        ),
    },

    # ── Product co-buys (OFTEN_WITH) ───────────────────────────────────────
    {
        "question": "Which products are frequently bought together?",
        "cypher": (
            "MATCH (p1:Product)-[r:OFTEN_WITH]->(p2:Product) "
            "RETURN p1, r, p2 "
            "ORDER BY r.strength DESC "
            "LIMIT 25"
        ),
    },
    {
        "question": "What is often bought with Atta?",
        "cypher": (
            "MATCH (p1:Product)-[r:OFTEN_WITH]->(p2:Product) "
            "WHERE p1.name CONTAINS 'Atta' "
            "RETURN p1, r, p2 "
            "ORDER BY r.strength DESC"
        ),
    },
    {
        "question": "Recommend products to suggest alongside Rice.",
        "cypher": (
            "MATCH (p1:Product)-[r:OFTEN_WITH]->(p2:Product) "
            "WHERE p1.name CONTAINS 'Rice' "
            "RETURN p1, r, p2 "
            "ORDER BY r.strength DESC"
        ),
    },

    # ── Supplier chain ─────────────────────────────────────────────────────
    {
        "question": "Where does Basmati Rice come from? Who supplies it?",
        "cypher": (
            "MATCH (p:Product)-[r:SUPPLIED_BY]->(s:Supplier) "
            "WHERE p.name CONTAINS 'Rice' "
            "RETURN p, r, s"
        ),
    },
    {
        "question": "Show all products and their suppliers.",
        "cypher": (
            "MATCH (p:Product)-[r:SUPPLIED_BY]->(s:Supplier) "
            "RETURN p, r, s "
            "LIMIT 25"
        ),
    },
    {
        "question": "Which supplier provides snacks?",
        "cypher": (
            "MATCH (p:Product)-[r:SUPPLIED_BY]->(s:Supplier) "
            "WHERE p.category = 'Snacks' "
            "RETURN p, r, s"
        ),
    },

    # ── Referrals ──────────────────────────────────────────────────────────
    {
        "question": "Who referred which customers to the store?",
        "cypher": (
            "MATCH (c:Customer)-[r:REFERRED_BY]->(ref:Customer) "
            "RETURN c, r, ref"
        ),
    },

    # ── Full graph overview ────────────────────────────────────────────────
    {
        "question": "Show the full customer and product network.",
        "cypher": (
            "MATCH (c:Customer)-[r:PURCHASED]->(p:Product) "
            "RETURN c, r, p "
            "LIMIT 20"
        ),
    },
    {
        "question": "Show customers and their khata connections.",
        "cypher": (
            "MATCH (c:Customer)-[r:OWES]->(k:Khata) "
            "RETURN c, r, k"
        ),
    },
]
