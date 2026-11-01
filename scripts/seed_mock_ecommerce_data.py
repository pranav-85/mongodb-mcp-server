"""
Seed a realistic e-commerce test database for the MongoDB MCP learning project.

Install:
    pip install "pymongo[srv]" Faker python-dotenv

Run:
    python scripts/seed_database.py

Environment (.env):
    MONGODB_URI=mongodb+srv://<username>:<password>@<cluster-host>/
    MONGODB_DATABASE=ecommerce
    RESET_DATABASE=false

Safety:
    The script refuses to overwrite an existing ecommerce database unless
    RESET_DATABASE=true. If true, it drops ONLY the database named in
    MONGODB_DATABASE before recreating the mock dataset.
"""

from __future__ import annotations

import os
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from dotenv import load_dotenv
from faker import Faker
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import PyMongoError

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("MONGODB_DATABASE", "ecommerce")
RESET_DATABASE = os.getenv("RESET_DATABASE", "false").lower() == "true"

COUNTS = {
    "customers": 1_000,
    "products": 250,
    "orders": 3_000,
    "payments": 3_000,
    "reviews": 1_500,
}

SEED = 42
random.seed(SEED)
fake = Faker("en_IN")
Faker.seed(SEED)

CITIES = [
    ("Hyderabad", "Telangana", "500081"),
    ("Bengaluru", "Karnataka", "560001"),
    ("Mumbai", "Maharashtra", "400001"),
    ("Pune", "Maharashtra", "411001"),
    ("Chennai", "Tamil Nadu", "600001"),
    ("Delhi", "Delhi", "110001"),
    ("Kolkata", "West Bengal", "700001"),
    ("Jaipur", "Rajasthan", "302001"),
    ("Kochi", "Kerala", "682001"),
    ("Ahmedabad", "Gujarat", "380001"),
]

CATEGORIES = {
    "Electronics": ["Headphones", "Smartphone", "Keyboard", "Mouse", "Monitor", "Speaker"],
    "Fashion": ["T-Shirt", "Jeans", "Sneakers", "Jacket", "Backpack", "Watch"],
    "Home": ["Desk Lamp", "Cookware Set", "Bedsheet", "Storage Rack", "Coffee Maker"],
    "Books": ["Programming Book", "Business Book", "Novel", "Cookbook", "Biography"],
    "Sports": ["Yoga Mat", "Running Shoes", "Dumbbell Set", "Cricket Bat", "Water Bottle"],
}

BRANDS = ["Nova", "UrbanLeaf", "SoundMax", "Peak", "HomeCraft", "Vertex", "DailyCo"]
MEMBERSHIP_TIERS = ["Standard", "Silver", "Gold", "Platinum"]
ORDER_STATUSES = ["Delivered", "Shipped", "Processing", "Cancelled", "Returned"]
PAYMENT_METHODS = ["UPI", "Credit Card", "Debit Card", "Net Banking", "Wallet"]
PAYMENT_STATUSES = ["Success", "Success", "Success", "Pending", "Failed"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def random_past_date(days: int = 540) -> datetime:
    return utc_now() - timedelta(
        days=random.randint(0, days),
        seconds=random.randint(0, 86_399),
    )


def money(value: float) -> float:
    return round(value, 2)


def make_customers() -> list[dict[str, Any]]:
    customers = []
    for i in range(1, COUNTS["customers"] + 1):
        city, state, pincode = random.choice(CITIES)
        joined_at = random_past_date(1_000)
        customers.append({
            "customer_id": f"CUST{i:05d}",
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "email": f"customer{i:05d}@example.test",
            "phone": f"+91{random.randint(6000000000, 9999999999)}",
            "gender": random.choice(["Female", "Male", "Non-binary", "Prefer not to say"]),
            "age": random.randint(18, 75),
            "address": {
                "city": city,
                "state": state,
                "country": "India",
                "pincode": pincode,
            },
            "membership": {
                "tier": random.choices(
                    MEMBERSHIP_TIERS, weights=[55, 25, 15, 5], k=1
                )[0],
                "joined_at": joined_at,
            },
            "created_at": joined_at,
            "is_active": random.random() > 0.08,
        })
    return customers


def make_products() -> list[dict[str, Any]]:
    products = []
    for i in range(1, COUNTS["products"] + 1):
        category = random.choice(list(CATEGORIES))
        item_name = random.choice(CATEGORIES[category])
        price = money(random.uniform(199, 75_000))
        products.append({
            "product_id": f"PROD{i:04d}",
            "name": f"{random.choice(BRANDS)} {item_name}",
            "category": category,
            "brand": random.choice(BRANDS),
            "price": price,
            "cost_price": money(price * random.uniform(0.45, 0.78)),
            "stock": random.randint(0, 250),
            "specifications": {
                "color": random.choice(["Black", "White", "Blue", "Green", "Grey"]),
                "warranty_months": random.choice([0, 6, 12, 24]),
                "origin": "India",
            },
            "tags": random.sample(
                ["popular", "new-arrival", "bestseller", "sale", "premium", "eco-friendly"],
                k=random.randint(1, 3),
            ),
            "rating": round(random.uniform(2.5, 5.0), 1),
            "created_at": random_past_date(700),
        })
    return products


def make_orders(
    customers: list[dict[str, Any]],
    products: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    orders = []
    payments = []
    products_by_id = {p["product_id"]: p for p in products}

    for i in range(1, COUNTS["orders"] + 1):
        customer = random.choice(customers)
        ordered_at = random_past_date(540)
        status = random.choices(
            ORDER_STATUSES, weights=[58, 15, 13, 9, 5], k=1
        )[0]

        chosen_products = random.sample(products, k=random.randint(1, 4))
        items = []
        subtotal = 0.0

        for product in chosen_products:
            quantity = random.randint(1, 3)
            unit_price = product["price"]
            line_total = unit_price * quantity
            subtotal += line_total
            items.append({
                "product_id": product["product_id"],
                "product_name": product["name"],
                "category": product["category"],
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": money(line_total),
            })

        discount = money(subtotal * random.choice([0, 0, 0.05, 0.10, 0.15]))
        tax = money((subtotal - discount) * 0.18)
        total = money(subtotal - discount + tax)

        city, state, _ = random.choice(CITIES)
        order_id = f"ORD{i:06d}"
        delivered_at = (
            ordered_at + timedelta(days=random.randint(1, 9))
            if status == "Delivered"
            else None
        )

        orders.append({
            "order_id": order_id,
            "customer_id": customer["customer_id"],
            "items": items,
            "subtotal": money(subtotal),
            "discount": discount,
            "tax": tax,
            "total_amount": total,
            "currency": "INR",
            "status": status,
            "shipping_address": {
                "city": city,
                "state": state,
                "country": "India",
            },
            "ordered_at": ordered_at,
            "delivered_at": delivered_at,
        })

        payment_status = (
            "Failed" if status == "Cancelled" and random.random() < 0.35
            else random.choice(PAYMENT_STATUSES)
        )
        payments.append({
            "payment_id": f"PAY{i:06d}",
            "order_id": order_id,
            "customer_id": customer["customer_id"],
            "payment_method": random.choice(PAYMENT_METHODS),
            "amount": total,
            "currency": "INR",
            "status": payment_status,
            "transaction_reference": f"TXN{random.randint(10**9, 10**10 - 1)}",
            "paid_at": ordered_at + timedelta(minutes=random.randint(1, 90)),
        })

    return orders, payments


def make_reviews(
    customers: list[dict[str, Any]],
    products: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    reviews = []
    review_texts = [
        "Good value for money and works as expected.",
        "Quality is excellent. Would recommend.",
        "Product is fine, but delivery could be faster.",
        "Not quite what I expected from the description.",
        "Great experience. I would purchase again.",
        "Average product with a few minor issues.",
        "Packaging was good and the product arrived safely.",
    ]

    for i in range(1, COUNTS["reviews"] + 1):
        customer = random.choice(customers)
        product = random.choice(products)
        reviews.append({
            "review_id": f"REV{i:05d}",
            "product_id": product["product_id"],
            "customer_id": customer["customer_id"],
            "rating": random.choices([1, 2, 3, 4, 5], weights=[4, 7, 15, 34, 40], k=1)[0],
            "review_text": random.choice(review_texts),
            "verified_purchase": random.random() > 0.12,
            "created_at": random_past_date(540),
        })
    return reviews


def create_indexes(db) -> None:
    db.customers.create_index([("customer_id", ASCENDING)], unique=True)
    db.customers.create_index([("email", ASCENDING)], unique=True)
    db.customers.create_index([("address.city", ASCENDING)])

    db.products.create_index([("product_id", ASCENDING)], unique=True)
    db.products.create_index([("category", ASCENDING), ("price", ASCENDING)])
    db.products.create_index([("tags", ASCENDING)])

    db.orders.create_index([("order_id", ASCENDING)], unique=True)
    db.orders.create_index([("customer_id", ASCENDING), ("ordered_at", DESCENDING)])
    db.orders.create_index([("status", ASCENDING), ("ordered_at", DESCENDING)])

    db.payments.create_index([("payment_id", ASCENDING)], unique=True)
    db.payments.create_index([("order_id", ASCENDING)], unique=True)
    db.payments.create_index([("customer_id", ASCENDING)])

    db.reviews.create_index([("review_id", ASCENDING)], unique=True)
    db.reviews.create_index([("product_id", ASCENDING), ("rating", DESCENDING)])
    db.reviews.create_index([("customer_id", ASCENDING)])


def insert_in_batches(collection, documents: list[dict[str, Any]]) -> None:
    batch_size = 500
    for start in range(0, len(documents), batch_size):
        collection.insert_many(documents[start:start + batch_size], ordered=False)


def main() -> None:
    if not MONGODB_URI:
        raise SystemExit("Missing MONGODB_URI. Add it to your .env file.")

    if DATABASE_NAME != "ecommerce":
        raise SystemExit(
            "Safety check: this seed script is intended for the ecommerce "
            "database. Set MONGODB_DATABASE=ecommerce."
        )

    client = MongoClient(
        MONGODB_URI,
        serverSelectionTimeoutMS=10_000,
        appname="mongodb-mcp-learning-seeder",
    )

    try:
        client.admin.command("ping")
        print("Connected to MongoDB successfully.")

        db = client[DATABASE_NAME]
        existing = client.list_database_names()

        if DATABASE_NAME in existing and db.list_collection_names():
            if not RESET_DATABASE:
                raise SystemExit(
                    f"{DATABASE_NAME} already contains collections. "
                    "To replace this test dataset, set RESET_DATABASE=true "
                    "after confirming the database contains no data you need."
                )
            print(f"Dropping existing test database: {DATABASE_NAME}")
            client.drop_database(DATABASE_NAME)
            db = client[DATABASE_NAME]

        print("Generating mock data...")
        customers = make_customers()
        products = make_products()
        orders, payments = make_orders(customers, products)
        reviews = make_reviews(customers, products)

        datasets = {
            "customers": customers,
            "products": products,
            "orders": orders,
            "payments": payments,
            "reviews": reviews,
        }

        for collection_name, documents in datasets.items():
            insert_in_batches(db[collection_name], documents)
            print(f"Inserted {len(documents):,} documents into {collection_name}")

        create_indexes(db)

        print("\nDatabase seeded successfully.")
        print(f"Database: {DATABASE_NAME}")
        print("Collections:")
        for collection_name in datasets:
            print(f"  {collection_name}: {db[collection_name].count_documents({}):,}")
        print("\nIndexes created successfully.")

    except PyMongoError as exc:
        raise SystemExit(f"MongoDB operation failed: {exc}") from exc
    finally:
        client.close()


if __name__ == "__main__":
    main()
