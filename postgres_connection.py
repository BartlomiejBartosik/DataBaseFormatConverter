import psycopg2


def test_postgres_connection(host, port, database, user, password):
    conn = None
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=database,
            user=user,
            password=password
        )
        return True
    except Exception as e:
        raise Exception(f"Błąd połączenia z PostgreSQL: {str(e)}")
    finally:
        if conn:
            conn.close()


def get_postgres_data(host, port, database, user, password, table_name="users"):
    conn = None
    cursor = None

    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=database,
            user=user,
            password=password
        )
        cursor = conn.cursor()

        query = f"SELECT * FROM {table_name}"
        cursor.execute(query)

        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        result = []
        for row in rows:
            row_dict = {}
            for i, value in enumerate(row):
                row_dict[columns[i]] = value
            result.append(row_dict)

        return result

    except Exception as e:
        raise Exception(f"Błąd odczytu danych z PostgreSQL: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()