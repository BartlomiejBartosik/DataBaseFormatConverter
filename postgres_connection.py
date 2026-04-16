import psycopg2


def test_postgres_connection(host, port, database, user, password):
    try:
        connection = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        connection.close()
        return True
    except Exception as e:
        print("Błąd PostgreSQL:", e)
        return False