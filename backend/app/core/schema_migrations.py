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
