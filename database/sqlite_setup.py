"""
SQLite setup for KiranaAI — structured data store.
Handles: inventory, transactions, billing, customers, suppliers.
"""
import sqlite3
import os
import random
from datetime import datetime, timedelta

DB_PATH = os.getenv("SQLITE_DB_PATH", "kirana_store.db")


def create_tables(conn: sqlite3.Connection):
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS suppliers (
        id   INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        contact TEXT,
        category TEXT
    );

    CREATE TABLE IF NOT EXISTS products (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        name           TEXT NOT NULL,
        category       TEXT NOT NULL,
        price          REAL NOT NULL,
        stock_quantity INTEGER NOT NULL DEFAULT 0,
        unit           TEXT NOT NULL DEFAULT 'packet',
        min_stock      INTEGER DEFAULT 10,
        supplier_id    INTEGER REFERENCES suppliers(id)
    );

    CREATE TABLE IF NOT EXISTS customers (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        name            TEXT NOT NULL,
        phone           TEXT,
        address         TEXT,
        registered_date DATE DEFAULT CURRENT_DATE
    );

    CREATE TABLE IF NOT EXISTS credit_accounts (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id  INTEGER NOT NULL REFERENCES customers(id),
        balance      REAL DEFAULT 0,
        credit_limit REAL DEFAULT 1000,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS transactions (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id  INTEGER REFERENCES customers(id),
        date         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        total_amount REAL NOT NULL,
        payment_mode TEXT DEFAULT 'cash',
        is_credit    INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS transaction_items (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_id INTEGER NOT NULL REFERENCES transactions(id),
        product_id     INTEGER NOT NULL REFERENCES products(id),
        quantity       REAL NOT NULL,
        unit_price     REAL NOT NULL
    );
    """)
    conn.commit()


def seed_data(conn: sqlite3.Connection):
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM products")
    if c.fetchone()[0] > 0:
        return  # Already seeded

    # ── Suppliers ──────────────────────────────────────────────
    suppliers = [
        ("Ram Distributors",  "9876543210", "Grocery"),
        ("Shyam Agencies",    "9876543211", "FMCG"),
        ("Gupta Wholesale",   "9876543212", "Staples"),
        ("Patel Brothers",    "9876543213", "Snacks"),
    ]
    c.executemany(
        "INSERT INTO suppliers (name, contact, category) VALUES (?,?,?)",
        suppliers
    )

    # ── Products (id 1-20) ─────────────────────────────────────
    # (name, category, price, stock, unit, min_stock, supplier_id)
    products = [
        ("Atta (5kg)",                "Staples",       220,  45, "packet", 10, 3),
        ("Basmati Rice (5kg)",        "Staples",       350,  38, "packet",  8, 3),
        ("Toor Dal (1kg)",            "Staples",       120,  55, "packet", 15, 3),
        ("Chana Dal (1kg)",           "Staples",       100,  42, "packet", 10, 3),
        ("Sugar (1kg)",               "Staples",        45,  80, "packet", 20, 3),
        ("Tea – Tata Gold (250g)",    "Beverages",      90,  30, "packet", 10, 2),
        ("Milk – Amul (1L)",          "Dairy",          60,   8, "litre",  10, 1),
        ("Refined Oil – Fortune (1L)","Cooking",       140,  28, "bottle", 10, 1),
        ("Salt (1kg)",                "Staples",        20, 100, "packet", 20, 3),
        ("Turmeric Powder (100g)",    "Spices",         35,  40, "packet", 10, 1),
        ("Red Chilli Powder (100g)",  "Spices",         40,  32, "packet", 10, 1),
        ("Parle-G Biscuits",          "Snacks",         10, 180, "packet", 50, 4),
        ("Lays Chips (26g)",          "Snacks",         20,  90, "packet", 30, 4),
        ("Lifebuoy Soap",             "Personal Care",  45,  55, "bar",    15, 2),
        ("Head & Shoulders Shampoo",  "Personal Care", 150,  22, "bottle",  8, 2),
        ("Colgate Toothpaste",        "Personal Care",  80,  38, "tube",   10, 2),
        ("Maggi 2-Min Noodles",       "Instant Food",   14, 140, "packet", 50, 4),
        ("Nescafe Classic (50g)",     "Beverages",     120,  18, "jar",     5, 2),
        ("Coconut Oil – Parachute",   "Cooking",       180,  14, "bottle",  5, 1),
        ("Ariel Washing Powder (1kg)","Household",      85,  36, "packet", 10, 2),
    ]
    c.executemany(
        "INSERT INTO products (name, category, price, stock_quantity, unit, min_stock, supplier_id)"
        " VALUES (?,?,?,?,?,?,?)",
        products
    )

    # ── Customers ──────────────────────────────────────────────
    customers = [
        ("Ramesh Kumar",  "9811111111", "12, Gandhi Nagar"),
        ("Sunita Devi",   "9822222222", "45, Shastri Colony"),
        ("Vijay Singh",   "9833333333", "7, Ram Nagar"),
        ("Priya Sharma",  "9844444444", "23, Nehru Road"),
        ("Mohan Lal",     "9855555555", "89, Patel Street"),
        ("Anita Rani",    "9866666666", "34, Vikas Nagar"),
        ("Suresh Yadav",  "9877777777", "56, Tilak Road"),
        ("Geeta Kumari",  "9888888888", "78, Laxmi Colony"),
    ]
    c.executemany(
        "INSERT INTO customers (name, phone, address) VALUES (?,?,?)",
        customers
    )

    # ── Credit / Khata accounts ────────────────────────────────
    khata = [
        (1, 250.0, 2000),  # Ramesh owes ₹250
        (2,   0.0, 1500),
        (3, 180.0, 1000),  # Vijay  owes ₹180
        (4,   0.0, 1000),
        (5, 450.0, 3000),  # Mohan  owes ₹450
        (6,   0.0, 1000),
        (7, 120.0, 1500),  # Suresh owes ₹120
        (8,   0.0, 1000),
    ]
    c.executemany(
        "INSERT INTO credit_accounts (customer_id, balance, credit_limit) VALUES (?,?,?)",
        khata
    )

    # ── Transactions – last 30 days ────────────────────────────
    # Typical basket per customer (product_id, qty)
    baskets = {
        1: [(1,1),(5,1),(6,1)],       # Ramesh: atta, sugar, tea
        2: [(2,1),(3,1),(14,2)],      # Sunita: rice, dal, soap
        3: [(1,2),(7,2),(12,5)],      # Vijay:  atta, milk, biscuits
        4: [(8,1),(5,1),(10,1)],      # Priya:  oil, sugar, turmeric
        5: [(4,2),(5,2),(17,3)],      # Mohan:  chana dal, sugar, maggi
        6: [(6,2),(18,1),(14,1)],     # Anita:  tea, coffee, soap
        7: [(1,1),(3,1),(16,1)],      # Suresh: atta, dal, toothpaste
        8: [(2,1),(7,2),(13,2)],      # Geeta:  rice, milk, chips
    }
    prod_prices = {i+1: p[2] for i, p in enumerate(products)}

    now = datetime.now()
    t_id = 1
    all_txns = []
    all_items = []

    for day in range(30, 0, -1):
        day_dt = now - timedelta(days=day)
        shoppers = random.sample(range(1, 9), random.randint(3, 6))
        for cid in shoppers:
            items = list(baskets[cid])
            if random.random() > 0.6:          # occasional extra item
                items.append((random.randint(1, 20), 1))

            total = sum(prod_prices.get(pid, 50) * qty for pid, qty in items)
            on_credit = cid in (1, 3, 5, 7) and random.random() > 0.5
            mode = "credit" if on_credit else random.choice(["cash", "cash", "upi"])

            all_txns.append((
                cid,
                day_dt.strftime("%Y-%m-%d %H:%M:%S"),
                round(total, 2),
                mode,
                int(on_credit),
            ))
            for pid, qty in items:
                all_items.append((t_id, pid, qty, prod_prices.get(pid, 50)))
            t_id += 1

    c.executemany(
        "INSERT INTO transactions (customer_id, date, total_amount, payment_mode, is_credit)"
        " VALUES (?,?,?,?,?)",
        all_txns,
    )
    c.executemany(
        "INSERT INTO transaction_items (transaction_id, product_id, quantity, unit_price)"
        " VALUES (?,?,?,?)",
        all_items,
    )
    conn.commit()
    print(f"✅ SQLite seeded: {len(all_txns)} transactions, {len(all_items)} line-items")


def setup_sqlite(db_path: str = DB_PATH) -> str:
    conn = sqlite3.connect(db_path)
    create_tables(conn)
    seed_data(conn)
    conn.close()
    return db_path


if __name__ == "__main__":
    path = setup_sqlite()
    print(f"Database ready at: {path}")
