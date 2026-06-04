from app.core.config import Settings


def test_settings_reads_database_url():
    settings = Settings(database_url="mysql+pymysql://sts:sts@localhost:3306/sts")

    assert settings.database_url == "mysql+pymysql://sts:sts@localhost:3306/sts"
    assert settings.jwt_algorithm == "HS256"


def test_cors_origins_are_split_from_csv():
    settings = Settings(cors_origins="http://localhost:5173,http://127.0.0.1:5173")

    assert settings.cors_origin_list == ["http://localhost:5173", "http://127.0.0.1:5173"]
