import json
from datetime import date, datetime
from decimal import Decimal

import psycopg2
import psycopg2.extras


POSTGRES_SCHEMA_KEY = "__postgres_schema__"


def get_postgres_connection(host, port, database, user, password):
    conn = psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        options="-c client_encoding=UTF8"
    )

    conn.set_client_encoding("UTF8")

    return conn


def test_postgres_connection(host, port, database, user, password):
    conn = None

    try:
        conn = get_postgres_connection(host, port, database, user, password)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        return True

    except Exception as e:
        print("Błąd PostgreSQL:", e)
        return False

    finally:
        if conn is not None:
            conn.close()


def get_postgres_tables(host, port, database, user, password):
    conn = None

    try:
        conn = get_postgres_connection(host, port, database, user, password)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)

        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()

        return tables

    finally:
        if conn is not None:
            conn.close()


def serialize_postgres_value(value):
    if isinstance(value, datetime) or isinstance(value, date):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, dict):
        return {
            key: serialize_postgres_value(val)
            for key, val in value.items()
        }

    if isinstance(value, list):
        return [
            serialize_postgres_value(item)
            for item in value
        ]

    return value


def table_has_column(cursor, table_name, column_name):
    cursor.execute("""
        SELECT COUNT(*) AS column_count
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = %s
        AND column_name = %s
    """, (table_name, column_name))

    row = cursor.fetchone()

    return row["column_count"] > 0


def get_all_postgres_tables_from_cursor(cursor):
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)

    rows = cursor.fetchall()

    return [row["table_name"] for row in rows]


def get_postgres_foreign_keys(cursor):
    cursor.execute("""
        SELECT
            tc.table_name AS child_table,
            kcu.column_name AS child_column,
            ccu.table_name AS parent_table,
            ccu.column_name AS parent_column
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND tc.table_schema = 'public'
        ORDER BY
            ccu.table_name,
            tc.table_name,
            kcu.column_name
    """)

    rows = cursor.fetchall()

    foreign_keys = []

    for row in rows:
        foreign_keys.append({
            "parent_table": row["parent_table"],
            "parent_column": row["parent_column"],
            "child_table": row["child_table"],
            "child_column": row["child_column"]
        })

    return foreign_keys


def get_related_tables_by_foreign_keys(selected_table, all_tables, foreign_keys):
    related_tables = set()
    related_tables.add(selected_table)

    changed = True

    while changed:
        changed = False

        for relation in foreign_keys:
            parent_table = relation["parent_table"]
            child_table = relation["child_table"]

            if parent_table in related_tables and child_table not in related_tables:
                related_tables.add(child_table)
                changed = True

            if child_table in related_tables and parent_table not in related_tables:
                related_tables.add(parent_table)
                changed = True

    return [
        table
        for table in all_tables
        if table in related_tables
    ]


def get_related_tables_by_converter_names(selected_table, all_tables):
    related_tables = []

    for table in all_tables:
        if table == selected_table or table.startswith(selected_table + "_"):
            related_tables.append(table)

    return related_tables


def get_related_tables_for_selected_table(cursor, selected_table):
    all_tables = get_all_postgres_tables_from_cursor(cursor)
    foreign_keys = get_postgres_foreign_keys(cursor)

    if selected_table not in all_tables:
        return [selected_table], foreign_keys

    tables_from_foreign_keys = get_related_tables_by_foreign_keys(
        selected_table,
        all_tables,
        foreign_keys
    )

    tables_from_converter_names = get_related_tables_by_converter_names(
        selected_table,
        all_tables
    )

    related_tables = set()
    related_tables.update(tables_from_foreign_keys)
    related_tables.update(tables_from_converter_names)

    ordered_tables = [
        table
        for table in all_tables
        if table in related_tables
    ]

    ordered_tables.sort(key=lambda name: name.count("_"))

    return ordered_tables, foreign_keys


def read_postgres_to_intermediate(
    host,
    port,
    database,
    user,
    password,
    selected_table=None
):
    conn = None
    intermediate_data = {}

    try:
        conn = get_postgres_connection(host, port, database, user, password)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        if selected_table:
            tables, foreign_keys = get_related_tables_for_selected_table(
                cursor,
                selected_table
            )
        else:
            tables = get_all_postgres_tables_from_cursor(cursor)
            foreign_keys = get_postgres_foreign_keys(cursor)

        for table in tables:
            cursor.execute(f'SELECT * FROM "{table}"')
            rows = cursor.fetchall()

            converted_rows = []

            for row in rows:
                converted_row = {}

                for column, value in dict(row).items():
                    converted_row[column] = serialize_postgres_value(value)

                converted_rows.append(converted_row)

            intermediate_data[table] = converted_rows

        filtered_foreign_keys = []
        selected_tables_set = set(tables)

        for relation in foreign_keys:
            if (
                relation["parent_table"] in selected_tables_set
                and relation["child_table"] in selected_tables_set
            ):
                filtered_foreign_keys.append(relation)

        if filtered_foreign_keys:
            intermediate_data[POSTGRES_SCHEMA_KEY] = {
                "foreign_keys": filtered_foreign_keys,
                "selected_table": selected_table
            }

        cursor.close()

        return intermediate_data

    finally:
        if conn is not None:
            conn.close()


def infer_postgres_type(value):
    if isinstance(value, bool):
        return "BOOLEAN"

    if isinstance(value, int):
        return "INTEGER"

    if isinstance(value, float):
        return "DOUBLE PRECISION"

    if isinstance(value, datetime):
        return "TIMESTAMP"

    if isinstance(value, date):
        return "DATE"

    return "TEXT"


def normalize_column_value(value):
    if isinstance(value, datetime) or isinstance(value, date):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, dict) or isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)

    return value


def is_simple_value(value):
    return not isinstance(value, dict) and not isinstance(value, list)


def clean_table_name(name):
    cleaned = str(name).replace(" ", "_").replace("-", "_")

    allowed_chars = []

    for char in cleaned:
        if char.isalnum() or char == "_":
            allowed_chars.append(char)

    cleaned = "".join(allowed_chars)

    if not cleaned:
        cleaned = "table"

    return cleaned.lower()


def get_sample_value(records, column):
    for record in records:
        if column in record and record[column] is not None:
            return record[column]

    return None


def generate_converter_id(table_name, index):
    return f"{table_name}_{index + 1}"


def flatten_records_for_postgres(
    table_name,
    records,
    parent_table=None,
    parent_id=None,
    generated_tables=None
):
    if generated_tables is None:
        generated_tables = {}

    table_name = clean_table_name(table_name)

    if table_name not in generated_tables:
        generated_tables[table_name] = []

    for record in records:
        if not isinstance(record, dict):
            record = {
                "value": record
            }

        converter_id = record.get("__converter_id")

        if converter_id is None:
            converter_id = generate_converter_id(
                table_name,
                len(generated_tables[table_name])
            )

        main_record = {
            "__converter_id": converter_id
        }

        if parent_id is not None:
            main_record["__parent_id"] = parent_id

        for key, value in record.items():
            if key in ["__converter_id", "__parent_id"]:
                continue

            if is_simple_value(value):
                main_record[key] = normalize_column_value(value)

        generated_tables[table_name].append(main_record)

        for key, value in record.items():
            if key in ["__converter_id", "__parent_id"]:
                continue

            child_table_name = clean_table_name(f"{table_name}_{key}")

            if isinstance(value, dict):
                flatten_records_for_postgres(
                    table_name=child_table_name,
                    records=[value],
                    parent_table=table_name,
                    parent_id=converter_id,
                    generated_tables=generated_tables
                )

            elif isinstance(value, list):
                child_records = []

                for item in value:
                    if isinstance(item, dict):
                        child_records.append(item)
                    else:
                        child_records.append({
                            "value": item
                        })

                flatten_records_for_postgres(
                    table_name=child_table_name,
                    records=child_records,
                    parent_table=table_name,
                    parent_id=converter_id,
                    generated_tables=generated_tables
                )

    return generated_tables


def create_postgres_table(cursor, table_name, records):
    if not records:
        return []

    all_columns = set()

    for record in records:
        all_columns.update(record.keys())

    all_columns = list(all_columns)

    ordered_columns = []

    if "__converter_id" in all_columns:
        ordered_columns.append("__converter_id")
        all_columns.remove("__converter_id")

    if "__parent_id" in all_columns:
        ordered_columns.append("__parent_id")
        all_columns.remove("__parent_id")

    if "_id" in all_columns:
        ordered_columns.append("_id")
        all_columns.remove("_id")

    ordered_columns.extend(sorted(all_columns))

    column_definitions = []

    for column in ordered_columns:
        sample_value = get_sample_value(records, column)

        if column == "__converter_id":
            postgres_type = "TEXT PRIMARY KEY"

        elif column == "__parent_id":
            postgres_type = "TEXT"

        else:
            postgres_type = infer_postgres_type(sample_value)

        column_definitions.append(f'"{column}" {postgres_type}')

    create_query = f'''
        CREATE TABLE "{table_name}" (
            {", ".join(column_definitions)}
        )
    '''

    cursor.execute(create_query)

    return ordered_columns


def insert_records_to_postgres(cursor, table_name, records, columns):
    for record in records:
        insert_columns = []
        values = []
        placeholders = []

        for column in columns:
            insert_columns.append(f'"{column}"')
            values.append(normalize_column_value(record.get(column)))
            placeholders.append("%s")

        insert_query = f'''
            INSERT INTO "{table_name}" ({", ".join(insert_columns)})
            VALUES ({", ".join(placeholders)})
        '''

        cursor.execute(insert_query, values)


def find_parent_table_name(child_table_name, generated_tables):
    parts = child_table_name.split("_")

    while len(parts) > 1:
        parts = parts[:-1]
        possible_parent = "_".join(parts)

        if possible_parent in generated_tables:
            return possible_parent

    return None


def add_foreign_keys(cursor, generated_tables):
    for table_name, records in generated_tables.items():
        if not records:
            continue

        first_record = records[0]

        if "__parent_id" not in first_record:
            continue

        parent_table = find_parent_table_name(table_name, generated_tables)

        if parent_table is None:
            continue

        constraint_name = clean_table_name(f"fk_{table_name}_parent")

        try:
            cursor.execute(f'''
                ALTER TABLE "{table_name}"
                ADD CONSTRAINT "{constraint_name}"
                FOREIGN KEY ("__parent_id")
                REFERENCES "{parent_table}"("__converter_id")
                ON DELETE CASCADE
            ''')
        except Exception:
            pass


def write_intermediate_to_postgres(
    host,
    port,
    database,
    user,
    password,
    intermediate_data
):
    conn = None

    try:
        conn = get_postgres_connection(host, port, database, user, password)
        cursor = conn.cursor()

        generated_tables = {}

        for table_name, records in intermediate_data.items():
            if table_name.startswith("__"):
                continue

            if not records:
                continue

            flatten_records_for_postgres(
                table_name=table_name,
                records=records,
                generated_tables=generated_tables
            )

        table_names = list(generated_tables.keys())

        table_names.sort(key=lambda name: name.count("_"))

        for table_name in reversed(table_names):
            cursor.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')

        created_columns = {}

        for table_name in table_names:
            records = generated_tables[table_name]

            if not records:
                continue

            columns = create_postgres_table(cursor, table_name, records)
            created_columns[table_name] = columns

        add_foreign_keys(cursor, generated_tables)

        for table_name in table_names:
            records = generated_tables[table_name]

            if not records:
                continue

            insert_records_to_postgres(
                cursor,
                table_name,
                records,
                created_columns[table_name]
            )

        conn.commit()
        cursor.close()

    except Exception:
        if conn is not None:
            conn.rollback()
        raise

    finally:
        if conn is not None:
            conn.close()