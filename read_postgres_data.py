from sqlalchemy import text
from postgres_connection import get_postgres_engine

engine = get_postgres_engine()

with engine.connect() as connection:
    result = connection.execute(text("SELECT * FROM users"))

    print("Dane z tabeli users:")
    for row in result:
        print(row)