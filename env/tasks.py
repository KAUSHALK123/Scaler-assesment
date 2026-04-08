# env/tasks.py
import sqlite3
import textwrap
from dataclasses import dataclass
from typing import Optional


# ─────────────────────────────────────────────
# DB SETUP HELPERS
# ─────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    """In-memory SQLite connection, fresh each time."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def setup_ecommerce_db(conn: sqlite3.Connection) -> None:
    """Shared schema used across all 3 tasks."""
    conn.executescript(textwrap.dedent("""
        CREATE TABLE customers (
            id       INTEGER PRIMARY KEY,
            name     TEXT    NOT NULL,
            email    TEXT    NOT NULL UNIQUE,
            country  TEXT    NOT NULL
        );

        CREATE TABLE orders (
            id          INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL REFERENCES customers(id),
            status      TEXT    NOT NULL,
            total       REAL    NOT NULL,
            created_at  TEXT    NOT NULL
        );

        CREATE TABLE order_items (
            id         INTEGER PRIMARY KEY,
            order_id   INTEGER NOT NULL REFERENCES orders(id),
            product    TEXT    NOT NULL,
            quantity   INTEGER NOT NULL,
            unit_price REAL    NOT NULL
        );

        INSERT INTO customers VALUES
            (1,'Alice','alice@example.com','US'),
            (2,'Bob','bob@example.com','UK'),
            (3,'Carol','carol@example.com','US'),
            (4,'Dave','dave@example.com','IN'),
            (5,'Eve','eve@example.com','UK');

        INSERT INTO orders VALUES
            (1,1,'delivered',250.00,'2024-01-10'),
            (2,1,'delivered',89.99,'2024-02-15'),
            (3,2,'shipped',430.00,'2024-03-01'),
            (4,3,'pending',120.00,'2024-03-05'),
            (5,3,'cancelled',60.00,'2024-01-20'),
            (6,4,'delivered',310.00,'2024-02-28'),
            (7,5,'delivered',95.00,'2024-03-10'),
            (8,2,'delivered',200.00,'2024-01-05'),
            (9,4,'shipped',175.00,'2024-03-12'),
            (10,1,'pending',50.00,'2024-03-15');

        INSERT INTO order_items VALUES
            (1,1,'Laptop Stand',1,250.00),
            (2,2,'USB Hub',1,89.99),
            (3,3,'Mechanical Keyboard',1,430.00),
            (4,4,'Mouse Pad',2,60.00),
            (5,5,'HDMI Cable',1,60.00),
            (6,6,'Webcam',1,310.00),
            (7,7,'Headphones',1,95.00),
            (8,8,'Monitor',1,200.00),
            (9,9,'Desk Lamp',1,175.00),
            (10,10,'Notebook',5,10.00);
    """))


# ─────────────────────────────────────────────
# TASK DEFINITIONS
# ─────────────────────────────────────────────

@dataclass
class Task:
    task_id: str
    difficulty: str
    description: str
    schema_description: str
    broken_query: str
    correct_query: str
    hint: Optional[str]


SCHEMA_DESC = """
Tables:
  customers(id, name, email, country)
  orders(id, customer_id, status, total, created_at)
    status values: 'pending','shipped','delivered','cancelled'
  order_items(id, order_id, product, quantity, unit_price)
""".strip()


TASKS: dict[str, Task] = {

    # ── EASY ──────────────────────────────────
    "task_easy": Task(
        task_id="task_easy",
        difficulty="easy",
        description=(
            "The query below has syntax errors and will not run. "
            "Fix it so it returns the name and email of all customers from the US."
        ),
        schema_description=SCHEMA_DESC,
        broken_query=textwrap.dedent("""\
            SELEC name email
            FORM customers
            WEHRE country = 'US'
        """).strip(),
        correct_query=textwrap.dedent("""\
            SELECT name, email FROM customers WHERE country = 'US'
        """).strip(),
        hint="Check your keywords: SELECT, FROM, WHERE — and don't forget the comma.",
    ),

    # ── MEDIUM ────────────────────────────────
    "task_medium": Task(
        task_id="task_medium",
        difficulty="medium",
        description=(
            "The query below runs without error but returns wrong results. "
            "Fix it so it returns each customer's name and their total spend "
            "across delivered orders only, ordered by total spend descending. "
            "Only include customers who have at least one delivered order."
        ),
        schema_description=SCHEMA_DESC,
        broken_query=textwrap.dedent("""\
            SELECT c.name, SUM(o.total) AS total_spend
            FROM customers c
            JOIN orders o ON c.id = o.customer_id
            GROUP BY c.name
            ORDER BY total_spend DESC
        """).strip(),
        correct_query=textwrap.dedent("""\
            SELECT c.name, SUM(o.total) AS total_spend
            FROM customers c
            JOIN orders o ON c.id = o.customer_id
            WHERE o.status = 'delivered'
            GROUP BY c.name
            ORDER BY total_spend DESC
        """).strip(),
        hint="Think about which orders should be included before aggregating.",
    ),

    # ── HARD ──────────────────────────────────
    "task_hard": Task(
        task_id="task_hard",
        difficulty="hard",
        description=(
            "The query below is logically correct but extremely inefficient — "
            "it uses a correlated subquery that runs once per row. "
            "Rewrite it to use a JOIN or window function so it produces the same results "
            "but without the correlated subquery. "
            "Return: customer name, their most recent order date, and their total number of orders."
        ),
        schema_description=SCHEMA_DESC,
        broken_query=textwrap.dedent("""\
            SELECT
                c.name,
                (SELECT MAX(o2.created_at)
                 FROM orders o2
                 WHERE o2.customer_id = c.id) AS last_order_date,
                (SELECT COUNT(*)
                 FROM orders o3
                 WHERE o3.customer_id = c.id) AS order_count
            FROM customers c
        """).strip(),
        correct_query=textwrap.dedent("""\
            SELECT
                c.name,
                MAX(o.created_at) AS last_order_date,
                COUNT(o.id)       AS order_count
            FROM customers c
            LEFT JOIN orders o ON o.customer_id = c.id
            GROUP BY c.id, c.name
        """).strip(),
        hint=(
            "Replace correlated subqueries with a single LEFT JOIN + GROUP BY. "
            "Use MAX() and COUNT() in the outer query."
        ),
    ),
}


# ─────────────────────────────────────────────
# QUERY RUNNER
# ─────────────────────────────────────────────

def run_query(sql: str, conn: sqlite3.Connection) -> tuple[list[dict], Optional[str]]:
    """
    Execute sql against conn.
    Returns (rows, error_message). rows is [] on error.
    """
    try:
        cursor = conn.execute(sql)
        rows = [dict(r) for r in cursor.fetchall()]
        return rows, None
    except Exception as exc:
        return [], str(exc)


# ─────────────────────────────────────────────
# NORMALIZE HELPER
# ─────────────────────────────────────────────

def normalize_rows(rows: list[dict]) -> list[dict]:
    """
    Normalize float values to 2 decimal places for fair comparison.
    Prevents floating point precision mismatches in grader.
    """
    result = []
    for row in rows:
        normalized = {}
        for k, v in row.items():
            if isinstance(v, float):
                normalized[k] = round(v, 2)
            else:
                normalized[k] = v
        result.append(normalized)
    return result


# ─────────────────────────────────────────────
# GRADERS — deterministic, 0.0 → 1.0
# ─────────────────────────────────────────────

def grade(task_id: str, submitted_sql: str) -> tuple[float, dict[str, float], str]:
    """
    Returns (total_score, breakdown, message).
    Breakdown keys: syntax, schema, row_count, exact_match
    Each checkpoint worth 0.25 — total max 1.0
    """
    task = TASKS[task_id]
    breakdown: dict[str, float] = {
        "syntax":      0.0,
        "schema":      0.0,
        "row_count":   0.0,
        "exact_match": 0.0,
    }

    conn = get_connection()
    setup_ecommerce_db(conn)

    # ── 1. Syntax / runs without error (0.25) ──
    submitted_rows, error = run_query(submitted_sql, conn)
    if error:
        conn.close()
        msg = f"Query failed to execute: {error}"
        return 0.0, breakdown, msg
    breakdown["syntax"] = 0.25

    # ── 2. Get expected rows ──
    expected_rows, _ = run_query(task.correct_query, conn)

    # ── 3. Schema match — same column names (0.25) ──
    submitted_cols = set(submitted_rows[0].keys()) if submitted_rows else set()
    expected_cols  = set(expected_rows[0].keys())  if expected_rows  else set()
    if submitted_cols == expected_cols:
        breakdown["schema"] = 0.25

    # ── 4. Row count match (0.25) ──
    if len(submitted_rows) == len(expected_rows):
        breakdown["row_count"] = 0.25

    # ── 5. Exact match — normalize floats then compare (0.25) ──
    if normalize_rows(submitted_rows) == normalize_rows(expected_rows):
        breakdown["exact_match"] = 0.25

    conn.close()

    total = sum(breakdown.values())
    message = _grade_message(total, breakdown)
    return round(total, 4), breakdown, message


def _grade_message(total: float, breakdown: dict) -> str:
    if total == 1.0:
        return "Perfect score — query is correct and efficient."
    parts = []
    if breakdown["syntax"]      == 0: parts.append("query has syntax/runtime errors")
    if breakdown["schema"]      == 0: parts.append("column names don't match expected")
    if breakdown["row_count"]   == 0: parts.append("wrong number of rows returned")
    if breakdown["exact_match"] == 0: parts.append("values or ordering differ from expected")
    return "Partial credit. Issues: " + "; ".join(parts) + "."