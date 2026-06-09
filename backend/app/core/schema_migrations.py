from sqlalchemy import Engine, inspect, text


def ensure_development_schema(engine: Engine) -> None:
    """Apply tiny dev-only schema additions until formal migrations are introduced."""
    inspector = inspect(engine)
    for table_name in ("forum_posts", "forum_comments"):
        if not inspector.has_table(table_name):
            continue
        column_names = {column["name"] for column in inspector.get_columns(table_name)}
        with engine.begin() as connection:
            if "review_reason" not in column_names:
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN review_reason TEXT"))
            if table_name == "forum_posts" and "related_type" not in column_names:
                connection.execute(text("ALTER TABLE forum_posts ADD COLUMN related_type VARCHAR(40)"))
            if table_name == "forum_posts" and "related_id" not in column_names:
                connection.execute(text("ALTER TABLE forum_posts ADD COLUMN related_id INTEGER"))

    if inspector.has_table("backtest_timeline_items"):
        column_names = {
            column["name"] for column in inspector.get_columns("backtest_timeline_items")
        }
        if "item_id" not in column_names:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE backtest_timeline_items "
                        "ADD COLUMN item_id VARCHAR(80) NOT NULL DEFAULT ''"
                    )
                )

    if inspector.has_table("market_kline_cache"):
        column_names = {column["name"] for column in inspector.get_columns("market_kline_cache")}
        with engine.begin() as connection:
            if "source" not in column_names:
                connection.execute(
                    text(
                        "ALTER TABLE market_kline_cache "
                        "ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN'"
                    )
                )
            for column_name in ("open_price", "high_price", "low_price"):
                if column_name not in column_names:
                    connection.execute(
                        text(f"ALTER TABLE market_kline_cache ADD COLUMN {column_name} FLOAT")
                    )
                connection.execute(
                    text(
                        f"UPDATE market_kline_cache "
                        f"SET {column_name} = close "
                        f"WHERE {column_name} IS NULL"
                    )
                )
