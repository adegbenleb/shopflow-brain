"""Load ShopFlow gold tables from Postgres into Neo4j as a graph."""

import os

import psycopg
from dotenv import load_dotenv
from neo4j import GraphDatabase
from psycopg.rows import dict_row

load_dotenv()

BATCH_SIZE = 5000

# Unique keys make loading fast and stop duplicate nodes.
CONSTRAINTS = [
    "CREATE CONSTRAINT customer_key IF NOT EXISTS FOR (n:Customer) REQUIRE n.key IS UNIQUE",
    "CREATE CONSTRAINT order_key IF NOT EXISTS FOR (n:Order) REQUIRE n.key IS UNIQUE",
    "CREATE CONSTRAINT product_key IF NOT EXISTS FOR (n:Product) REQUIRE n.key IS UNIQUE",
    "CREATE CONSTRAINT seller_key IF NOT EXISTS FOR (n:Seller) REQUIRE n.key IS UNIQUE",
    "CREATE CONSTRAINT category_key IF NOT EXISTS FOR (n:Category) REQUIRE n.key IS UNIQUE",
]

# Each step: a name, a SQL query that reads gold, and a Cypher query that writes the graph.
# Order matters: nodes must exist before relationships can link them.
STEPS = [
    (
        "customers",
        """select customer_key as key, tenant_id, city, state
           from analytics_gold.dim_customers""",
        """UNWIND $rows AS r
           MERGE (c:Customer {key: r.key})
           SET c.tenant_id = r.tenant_id, c.city = r.city, c.state = r.state""",
    ),
    (
        "sellers",
        """select seller_key as key, tenant_id, city, state
           from analytics_gold.dim_sellers""",
        """UNWIND $rows AS r
           MERGE (s:Seller {key: r.key})
           SET s.tenant_id = r.tenant_id, s.city = r.city, s.state = r.state""",
    ),
    (
        "products",
        """select product_key as key, tenant_id, product_id, category,
                  tenant_id || '|' || category as category_key
           from analytics_gold.dim_products""",
        """UNWIND $rows AS r
           MERGE (p:Product {key: r.key})
           SET p.tenant_id = r.tenant_id, p.product_id = r.product_id, p.category = r.category
           MERGE (cat:Category {key: r.category_key})
           SET cat.name = r.category, cat.tenant_id = r.tenant_id
           MERGE (p)-[:IN_CATEGORY]->(cat)""",
    ),
    (
        "orders",
        """select tenant_id || '|' || order_id as key, order_id, tenant_id, customer_key,
                  status, order_date, payment_total::float8 as total,
                  review_score::float8 as review_score, is_late, delivery_days
           from analytics_gold.fct_orders""",
        """UNWIND $rows AS r
           MERGE (o:Order {key: r.key})
           SET o.order_id = r.order_id, o.tenant_id = r.tenant_id, o.status = r.status,
               o.order_date = r.order_date, o.total = r.total,
               o.review_score = r.review_score, o.is_late = r.is_late,
               o.delivery_days = r.delivery_days
           WITH o, r
           MATCH (c:Customer {key: r.customer_key})
           MERGE (c)-[:PLACED]->(o)""",
    ),
    (
        "order items",
        """select tenant_id || '|' || order_id as order_key, line_number,
                  product_key, seller_key, price::float8 as price
           from analytics_gold.fct_order_items""",
        """UNWIND $rows AS r
           MATCH (o:Order {key: r.order_key})
           MATCH (p:Product {key: r.product_key})
           MERGE (o)-[i:CONTAINS {line_number: r.line_number}]->(p)
           SET i.price = r.price
           WITH p, r
           MATCH (s:Seller {key: r.seller_key})
           MERGE (p)-[:SOLD_BY]->(s)""",
    ),
]


def load_step(pg, session, name, sql, cypher):
    """Read one gold table in batches and write each batch to Neo4j."""
    total = 0
    with pg.cursor(row_factory=dict_row) as cur:
        cur.execute(sql)
        while rows := cur.fetchmany(BATCH_SIZE):
            session.run(cypher, rows=rows)
            total += len(rows)
            print(f"  {name}: {total} rows", end="\r")
    print(f"  {name}: {total} rows loaded")


def main():
    pg = psycopg.connect(os.environ["POSTGRES_URL"])
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
    )
    try:
        with driver.session() as session:
            for statement in CONSTRAINTS:
                session.run(statement)
            for name, sql, cypher in STEPS:
                load_step(pg, session, name, sql, cypher)
    finally:
        pg.close()
        driver.close()


if __name__ == "__main__":
    main()
