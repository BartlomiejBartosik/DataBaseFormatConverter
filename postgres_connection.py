from sqlalchemy import create_engine

DB_USER = "postgres"
DB_PASSWORD = "portal"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "db_converter"


def get_postgres_engine():
    DATABASE_URL = (
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    return create_engine(DATABASE_URL)