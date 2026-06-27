"""
Neo4j Community Edition setup for KiranaAI — graph data store.
Handles: customer relationships, purchase patterns, khata/credit,
         product recommendations (OFTEN_WITH), supplier tracing, referrals.
"""
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USERNAME", os.getenv("NEO4J_USER", "neo4j"))
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


def setup_neo4j():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    with driver.session() as s:
        # ── Wipe & constraints ──────────────────────────────────
        s.run("MATCH (n) DETACH DELETE n")
        for label in ("Customer", "Product", "Supplier"):
            s.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE")

        # ── Customer nodes ──────────────────────────────────────
        customers = [
            {"id": 1, "name": "Ramesh Kumar",  "phone": "9811111111", "area": "Gandhi Nagar"},
            {"id": 2, "name": "Sunita Devi",   "phone": "9822222222", "area": "Shastri Colony"},
            {"id": 3, "name": "Vijay Singh",   "phone": "9833333333", "area": "Ram Nagar"},
            {"id": 4, "name": "Priya Sharma",  "phone": "9844444444", "area": "Nehru Road"},
            {"id": 5, "name": "Mohan Lal",     "phone": "9855555555", "area": "Patel Street"},
            {"id": 6, "name": "Anita Rani",    "phone": "9866666666", "area": "Vikas Nagar"},
            {"id": 7, "name": "Suresh Yadav",  "phone": "9877777777", "area": "Tilak Road"},
            {"id": 8, "name": "Geeta Kumari",  "phone": "9888888888", "area": "Laxmi Colony"},
        ]
        for c in customers:
            s.run(
                "CREATE (c:Customer {id:$id, name:$name, phone:$phone, area:$area})",
                c
            )

        # ── Product nodes ───────────────────────────────────────
        products = [
            {"id":  1, "name": "Atta (5kg)",                "category": "Staples",       "price": 220},
            {"id":  2, "name": "Basmati Rice (5kg)",        "category": "Staples",       "price": 350},
            {"id":  3, "name": "Toor Dal (1kg)",            "category": "Staples",       "price": 120},
            {"id":  4, "name": "Chana Dal (1kg)",           "category": "Staples",       "price": 100},
            {"id":  5, "name": "Sugar (1kg)",               "category": "Staples",       "price":  45},
            {"id":  6, "name": "Tea – Tata Gold (250g)",    "category": "Beverages",     "price":  90},
            {"id":  7, "name": "Milk – Amul (1L)",          "category": "Dairy",         "price":  60},
            {"id":  8, "name": "Refined Oil (1L)",          "category": "Cooking",       "price": 140},
            {"id": 12, "name": "Parle-G Biscuits",          "category": "Snacks",        "price":  10},
            {"id": 13, "name": "Lays Chips",                "category": "Snacks",        "price":  20},
            {"id": 14, "name": "Lifebuoy Soap",             "category": "Personal Care", "price":  45},
            {"id": 16, "name": "Colgate Toothpaste",        "category": "Personal Care", "price":  80},
            {"id": 17, "name": "Maggi 2-Min Noodles",       "category": "Instant Food",  "price":  14},
            {"id": 18, "name": "Nescafe Classic (50g)",     "category": "Beverages",     "price": 120},
        ]
        for p in products:
            s.run(
                "CREATE (p:Product {id:$id, name:$name, category:$category, price:$price})",
                p
            )

        # ── Supplier nodes ──────────────────────────────────────
        suppliers = [
            {"id": 1, "name": "Ram Distributors", "category": "Grocery"},
            {"id": 2, "name": "Shyam Agencies",   "category": "FMCG"},
            {"id": 3, "name": "Gupta Wholesale",  "category": "Staples"},
            {"id": 4, "name": "Patel Brothers",   "category": "Snacks"},
        ]
        for sup in suppliers:
            s.run(
                "CREATE (s:Supplier {id:$id, name:$name, category:$category})",
                sup
            )

        # ── Khata (credit) nodes ─────────────────────────────────
        khata_data = [
            {"cid": 1, "balance": 250.0},
            {"cid": 3, "balance": 180.0},
            {"cid": 5, "balance": 450.0},
            {"cid": 7, "balance": 120.0},
        ]
        for k in khata_data:
            s.run("""
                MATCH (c:Customer {id: $cid})
                CREATE (kh:Khata {customer_id: $cid, balance: $balance, last_updated: date()})
                CREATE (c)-[:OWES]->(kh)
            """, k)

        # ── PURCHASED relationships ──────────────────────────────
        # (customer, [product_ids], avg_times_per_month)
        purchases = [
            (1, [1, 5,  6], 20),
            (2, [2, 3, 14], 18),
            (3, [1, 7, 12], 22),
            (4, [8, 5,  3], 15),
            (5, [4, 5, 17], 12),
            (6, [6,18, 14], 16),
            (7, [1, 3,  6], 19),
            (8, [2, 7, 13], 14),
        ]
        for cid, pids, times in purchases:
            for pid in pids:
                s.run("""
                    MATCH (c:Customer {id:$cid}), (p:Product {id:$pid})
                    CREATE (c)-[:PURCHASED {times:$times, last_date: date()}]->(p)
                """, {"cid": cid, "pid": pid, "times": times})

        # ── OFTEN_WITH relationships ─────────────────────────────
        # Products frequently bought together (p1_id, p2_id, strength 1-20)
        co_buys = [
            (1,  5, 15),   # Atta ↔ Sugar
            (1,  3, 18),   # Atta ↔ Toor Dal
            (2,  7, 12),   # Rice ↔ Milk
            (3,  1, 20),   # Dal  ↔ Atta
            (5,  6, 10),   # Sugar ↔ Tea
            (6, 18,  7),   # Tea  ↔ Nescafe
            (7,  2, 11),   # Milk ↔ Rice
            (12,13,  6),   # Biscuits ↔ Chips
            (17, 3,  8),   # Maggi ↔ Dal (for tadka)
        ]
        for p1, p2, strength in co_buys:
            s.run("""
                MATCH (a:Product {id:$p1}), (b:Product {id:$p2})
                CREATE (a)-[:OFTEN_WITH {strength:$strength}]->(b)
                CREATE (b)-[:OFTEN_WITH {strength:$strength}]->(a)
            """, {"p1": p1, "p2": p2, "strength": strength})

        # ── SUPPLIED_BY relationships ────────────────────────────
        supply = [
            (1, 3),(2, 3),(3, 3),(4, 3),(5, 3),    # Staples → Gupta Wholesale
            (6, 2),(14,2),(18,2),(16,2),             # FMCG   → Shyam Agencies
            (7, 1),(8, 1),                           # Grocery → Ram Distributors
            (12,4),(13,4),(17,4),                    # Snacks  → Patel Brothers
        ]
        for pid, sid in supply:
            s.run("""
                MATCH (p:Product {id:$pid}), (s:Supplier {id:$sid})
                CREATE (p)-[:SUPPLIED_BY]->(s)
            """, {"pid": pid, "sid": sid})

        # ── REFERRED_BY relationships ────────────────────────────
        referrals = [(3, 1), (6, 2), (8, 4)]   # new_cust_id → referrer_id
        for new_id, ref_id in referrals:
            s.run("""
                MATCH (new:Customer {id:$new_id}), (ref:Customer {id:$ref_id})
                CREATE (new)-[:REFERRED_BY]->(ref)
            """, {"new_id": new_id, "ref_id": ref_id})

    driver.close()
    print("✅ Neo4j graph seeded: customers, products, suppliers, khata, relationships")


if __name__ == "__main__":
    setup_neo4j()
