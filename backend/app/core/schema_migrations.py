from sqlalchemy import Engine, inspect, text


def ensure_development_schema(engine: Engine) -> None:
    """Apply tiny dev-only schema additions until formal migrations are introduced."""
    inspector = inspect(engine)
    for table_name in ("forum_posts", "forum_comments"):
        if not inspector.has_table(table_name):
            continue
        column_names = {column["name"] for column in inspector.get_columns(table_name)}
        if "review_reason" in column_names:
            continue
        with engine.begin() as connection:
            connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN review_reason TEXT"))
