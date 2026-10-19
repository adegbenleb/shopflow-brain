"""Curated, read-only tools the agent can call. Each one is a tested query with parameters."""

import json
import os

import psycopg
from dotenv import load_dotenv
from langchain_core.tools import tool
from neo4j import READ_ACCESS, GraphDatabase
from psycopg.rows import dict_row

load_dotenv()
TENANT = os.environ.get("TENANT_ID", "olist")


def _sql(query: str, params: tuple) -> str:
    with (
        psycopg.connect(os.environ["BRAIN_POSTGRES_URL"]) as conn,
        conn.cursor(row_factory=dict_row) as cur,
    ):
        cur.execute(query, params)
        return json.dumps(cur.fetchall(), default=str)


def _cypher(query: str, params: dict) -> str:
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
    )
    with driver, driver.session(default_access_mode=READ_ACCESS) as session:
        return json.dumps(
            [record.data() for record in session.run(query, params)], default=str
        )


def _clamp(limit: int) -> int:
    return max(1, min(int(limit), 50))


# Safe ranking options: the model picks a word, never raw SQL.
RANK_COLUMNS = {
    "spend": "total_spent",
    "orders": "orders",
    "items": "items",
}


@tool
def top_customers(
    limit: int = 10, rank_by: str = "spend", state: str | None = None
) -> str:
    """Customers ranked by total spend, number of orders or number of items bought.
    rank_by must be 'spend', 'orders' or 'items'. Customers are anonymous (masked ID).
    Optionally filter by a state code like SP."""
    order_column = RANK_COLUMNS.get(rank_by, "total_spent")
    return _sql(
        f"""select left(c.customer_key, 8) as customer,
                   c.city,
                   c.state,
                   count(distinct o.order_id) as orders,
                   coalesce(sum(o.item_count), 0) as items,
                   round(sum(o.payment_total), 2)::float8 as total_spent
            from analytics_gold.fct_orders o
            join analytics_gold.dim_customers c on c.customer_key = o.customer_key
            where o.tenant_id = %s
              and (%s::text is null or c.state = upper(%s))
            group by c.customer_key, c.city, c.state
            order by {order_column} desc
            limit %s""",
        (TENANT, state, state, _clamp(limit)),
    )


@tool
def sales_by_category(limit: int = 10) -> str:
    """Top product categories by revenue, with number of orders. Use for questions about best-selling categories."""
    return _sql(
        """select p.category,
                  count(distinct i.order_id) as orders,
                  round(sum(i.price), 2)::float8 as revenue
           from analytics_gold.fct_order_items i
           join analytics_gold.dim_products p on p.product_key = i.product_key
           where i.tenant_id = %s
           group by p.category
           order by revenue desc
           limit %s""",
        (TENANT, _clamp(limit)),
    )


@tool
def customers_by_state(limit: int = 10) -> str:
    """Customers, orders, revenue and average review score per Brazilian state (two-letter codes like SP, RJ)."""
    return _sql(
        """select c.state,
                  count(distinct c.customer_key) as customers,
                  count(o.order_id) as orders,
                  round(sum(o.payment_total), 2)::float8 as revenue,
                  round(avg(o.review_score), 2)::float8 as avg_review
           from analytics_gold.fct_orders o
           join analytics_gold.dim_customers c on c.customer_key = o.customer_key
           where o.tenant_id = %s
           group by c.state
           order by revenue desc
           limit %s""",
        (TENANT, _clamp(limit)),
    )


@tool
def delivery_performance(state: str | None = None) -> str:
    """Average delivery days and percent of late deliveries for delivered orders. Optionally for one state code."""
    return _sql(
        """select coalesce(%s, 'ALL') as state,
                  round(avg(o.delivery_days), 1)::float8 as avg_delivery_days,
                  round(100.0 * avg(case when o.is_late then 1 else 0 end), 1)::float8 as pct_late
           from analytics_gold.fct_orders o
           join analytics_gold.dim_customers c on c.customer_key = o.customer_key
           where o.tenant_id = %s
             and o.delivered_at is not null
             and (%s::text is null or c.state = upper(%s))""",
        (state, TENANT, state, state),
    )


@tool
def bought_together(category: str, limit: int = 5) -> str:
    """Categories most often bought in the same order as the given category. Category names are English, like bed_bath_table."""
    return _cypher(
        """MATCH (c1:Category {tenant_id: $tenant, name: $category})<-[:IN_CATEGORY]-(:Product)
                 <-[:CONTAINS]-(o:Order)-[:CONTAINS]->(:Product)-[:IN_CATEGORY]->(c2:Category)
           WHERE c2 <> c1
           RETURN c2.name AS category, count(DISTINCT o) AS orders
           ORDER BY orders DESC LIMIT $limit""",
        {"tenant": TENANT, "category": category, "limit": _clamp(limit)},
    )


@tool
def list_categories() -> str:
    """List all product category names. Use this first to find the exact name,
    for example 'beauty' is health_beauty and 'furniture' is furniture_decor."""
    return _sql(
        """select distinct category
           from analytics_gold.dim_products
           where tenant_id = %s
           order by category""",
        (TENANT,),
    )


PRODUCT_RANKS = {"revenue": "revenue", "units": "units"}


@tool
def top_products(
    category: str | None = None, limit: int = 10, rank_by: str = "revenue"
) -> str:
    """Best-selling individual products, ranked by revenue or units sold.
    rank_by must be 'revenue' or 'units'. Optionally only one category, using its exact name."""
    order_column = PRODUCT_RANKS.get(rank_by, "revenue")
    return _sql(
        f"""select left(p.product_id, 8) as product,
                   p.category,
                   count(*) as units,
                   count(distinct i.order_id) as orders,
                   round(sum(i.price), 2)::float8 as revenue
            from analytics_gold.fct_order_items i
            join analytics_gold.dim_products p on p.product_key = i.product_key
            where i.tenant_id = %s
              and (%s::text is null or p.category = %s)
            group by p.product_id, p.category
            order by {order_column} desc
            limit %s""",
        (TENANT, category, category, _clamp(limit)),
    )


TOOLS = [
    sales_by_category,
    list_categories,
    top_products,
    top_customers,
    customers_by_state,
    delivery_performance,
    bought_together,
]
