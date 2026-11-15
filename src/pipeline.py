"""Build the analytics warehouse.

raw CSVs  ->  staging tables (sql/staging)  ->  marts (sql/marts)  ->  data/marts/*.parquet

The parquet exports are small and committed to the repo so the Streamlit app can be
deployed without the raw data.
"""
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "warehouse.duckdb"
EXPORT_DIR = ROOT / "data" / "marts"

RAW_TABLES = {
    "raw_orders": "olist_orders_dataset.csv",
    "raw_customers": "olist_customers_dataset.csv",
    "raw_order_items": "olist_order_items_dataset.csv",
    "raw_payments": "olist_order_payments_dataset.csv",
    "raw_reviews": "olist_order_reviews_dataset.csv",
    "raw_products": "olist_products_dataset.csv",
    "raw_sellers": "olist_sellers_dataset.csv",
    "raw_category_translation": "product_category_name_translation.csv",
}

EXPORTS = ["mart_monthly_kpis", "mart_cohort_retention", "mart_funnel", "mart_rfm", "dim_customers"]


def run_sql_dir(con: duckdb.DuckDBPyConnection, folder: Path) -> None:
    for path in sorted(folder.glob("*.sql")):
        print(f"  running {path.relative_to(ROOT)}")
        con.execute(path.read_text())


def main() -> None:
    missing = [f for f in RAW_TABLES.values() if not (RAW / f).exists()]
    if missing:
        raise SystemExit(f"Missing raw files {missing}. Run `make data` first.")

    DB_PATH.unlink(missing_ok=True)
    con = duckdb.connect(str(DB_PATH))

    print("Loading raw CSVs")
    for table, file in RAW_TABLES.items():
        con.execute(f"create table {table} as select * from read_csv_auto('{RAW / file}', header=true)")

    print("Staging")
    run_sql_dir(con, ROOT / "sql" / "staging")
    print("Marts")
    run_sql_dir(con, ROOT / "sql" / "marts")

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    for table in EXPORTS:
        con.execute(f"copy {table} to '{EXPORT_DIR / table}.parquet' (format parquet)")
        n = con.execute(f"select count(*) from {table}").fetchone()[0]
        print(f"  exported {table}: {n:,} rows")

    run_tests(con)
    con.close()
    print(f"Warehouse ready: {DB_PATH.relative_to(ROOT)}")


def run_tests(con: duckdb.DuckDBPyConnection) -> None:
    """Lightweight data-quality tests (the dbt `unique` / `not_null` idea, in plain SQL)."""
    tests = {
        "fct_orders.order_id is unique":
            "select count(*) - count(distinct order_id) from fct_orders",
        "dim_customers.customer_unique_id is unique":
            "select count(*) - count(distinct customer_unique_id) from dim_customers",
        "fct_orders.gmv not null and positive":
            "select count(*) from fct_orders where gmv is null or gmv <= 0",
        "every customer has exactly one first order":
            "select count(*) from (select customer_unique_id from fct_orders where is_first_order "
            "group by 1 having count(*) <> 1)",
        "retention rate between 0 and 1":
            "select count(*) from mart_cohort_retention where retention_rate not between 0 and 1",
        "funnel is monotonically decreasing":
            "select count(*) from (select customers, lag(customers) over (order by step) prev "
            "from mart_funnel) where customers > prev",
    }
    print("Data tests")
    failed = 0
    for name, sql in tests.items():
        bad = con.execute(sql).fetchone()[0]
        status = "PASS" if bad == 0 else f"FAIL ({bad} rows)"
        failed += bad != 0
        print(f"  [{status}] {name}")
    if failed:
        raise SystemExit(f"{failed} data test(s) failed")


if __name__ == "__main__":
    main()
