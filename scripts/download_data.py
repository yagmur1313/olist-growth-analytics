"""Download the public Olist Brazilian E-commerce dataset into data/raw/.

Source: https://github.com/olist/work-at-olist-data (also on Kaggle:
https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). Licensed CC BY-NC-SA 4.0.
"""
from pathlib import Path
import urllib.request

BASE = "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets"
FILES = [
    "olist_customers_dataset",
    "olist_orders_dataset",
    "olist_order_items_dataset",
    "olist_order_payments_dataset",
    "olist_order_reviews_dataset",
    "olist_products_dataset",
    "olist_sellers_dataset",
    "product_category_name_translation",
]

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        target = RAW_DIR / f"{name}.csv"
        if target.exists():
            print(f"✓ {target.name} (already present)")
            continue
        print(f"↓ {target.name}")
        urllib.request.urlretrieve(f"{BASE}/{name}.csv", target)
    print(f"Done. Files are in {RAW_DIR}")


if __name__ == "__main__":
    main()
