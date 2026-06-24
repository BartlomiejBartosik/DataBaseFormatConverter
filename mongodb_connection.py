import time
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, date


POSTGRES_SCHEMA_KEY = "__postgres_schema__"


def get_mongo_client(host, port):
    uri = f"mongodb://{host}:{port}/"
    return MongoClient(uri, serverSelectionTimeoutMS=3000)


def test_mongo_connection(host, port, database):
    client = None

    try:
        client = get_mongo_client(host, port)
        client.admin.command("ping")

        db = client[database]
        db.list_collection_names()

        return True

    except Exception as e:
        print("Błąd MongoDB:", e)
        return False

    finally:
        if client is not None:
            client.close()


def get_mongo_collections(host, port, database):
    client = None

    try:
        client = get_mongo_client(host, port)
        db = client[database]
        return db.list_collection_names()

    finally:
        if client is not None:
            client.close()


def serialize_mongo_value(value):
    if isinstance(value, ObjectId):
        return str(value)

    if isinstance(value, datetime) or isinstance(value, date):
        return value.isoformat()

    if isinstance(value, list):
        return [serialize_mongo_value(item) for item in value]

    if isinstance(value, dict):
        return {key: serialize_mongo_value(val) for key, val in value.items()}

    return value


def restore_mongo_value(value):
    if isinstance(value, list):
        return [restore_mongo_value(item) for item in value]

    if isinstance(value, dict):
        return {key: restore_mongo_value(val) for key, val in value.items()}

    return value


def restore_object_id(record):
    if "_id" in record and isinstance(record["_id"], str):
        try:
            record["_id"] = ObjectId(record["_id"])
        except Exception:
            pass

    return record


def get_mongo_data(host, port, database, collection_name="osoby"):
    client = None

    try:
        client = get_mongo_client(host, port)
        db = client[database]
        collection = db[collection_name]

        data = []

        for document in collection.find():
            serialized_document = serialize_mongo_value(document)
            data.append(serialized_document)

        return data

    finally:
        if client is not None:
            client.close()


def read_mongo_to_intermediate(host, port, database, selected_collection=None):
    client = None
    intermediate_data = {}

    try:
        client = get_mongo_client(host, port)
        db = client[database]

        if selected_collection:
            collection_names = [selected_collection]
        else:
            collection_names = db.list_collection_names()

        for collection_name in collection_names:
            collection = db[collection_name]
            documents = []

            for document in collection.find():
                serialized_document = serialize_mongo_value(document)
                documents.append(serialized_document)

            intermediate_data[collection_name] = documents

        return intermediate_data

    finally:
        if client is not None:
            client.close()


def get_real_tables_from_intermediate(intermediate_data):
    tables = {}

    for table_name, records in intermediate_data.items():
        if table_name.startswith("__"):
            continue

        tables[table_name] = records

    return tables


def get_postgres_schema_metadata(intermediate_data):
    metadata = intermediate_data.get(POSTGRES_SCHEMA_KEY)

    if isinstance(metadata, dict):
        return metadata

    return {
        "foreign_keys": [],
        "selected_table": None
    }


def values_are_equal(left_value, right_value):
    if left_value == right_value:
        return True

    if left_value is None or right_value is None:
        return False

    return str(left_value) == str(right_value)


def is_converter_relation_data(intermediate_data):
    for table_name, records in intermediate_data.items():
        if table_name.startswith("__"):
            continue

        for record in records:
            if "__converter_id" in record or "__parent_id" in record:
                return True

    return False


def get_root_tables(intermediate_data):
    root_tables = []

    for table_name, records in intermediate_data.items():
        if table_name.startswith("__"):
            continue

        has_parent_id = False

        for record in records:
            if "__parent_id" in record:
                has_parent_id = True
                break

        if not has_parent_id:
            root_tables.append(table_name)

    return root_tables


def get_child_tables(parent_table, intermediate_data):
    child_tables = []
    prefix = parent_table + "_"

    for table_name, records in intermediate_data.items():
        if table_name.startswith("__"):
            continue

        if not table_name.startswith(prefix):
            continue

        has_parent_id = False

        for record in records:
            if "__parent_id" in record:
                has_parent_id = True
                break

        if has_parent_id:
            child_tables.append(table_name)

    child_tables.sort(key=lambda name: name.count("_"))

    return child_tables


def get_direct_child_tables(parent_table, intermediate_data):
    direct_children = []
    parent_depth = parent_table.count("_")

    for table_name in get_child_tables(parent_table, intermediate_data):
        if table_name.count("_") == parent_depth + 1:
            direct_children.append(table_name)

    return direct_children


def get_field_name_from_child_table(parent_table, child_table):
    prefix = parent_table + "_"

    if child_table.startswith(prefix):
        return child_table[len(prefix):]

    return child_table


def remove_converter_columns(record):
    cleaned = {}

    for key, value in record.items():
        if key in ["__converter_id", "__parent_id"]:
            continue

        cleaned[key] = value

    return cleaned


def is_simple_value_record(record):
    useful_keys = []

    for key in record.keys():
        if key not in ["__converter_id", "__parent_id"]:
            useful_keys.append(key)

    return useful_keys == ["value"]


def build_document_from_record(table_name, record, intermediate_data):
    document = remove_converter_columns(record)
    parent_converter_id = record.get("__converter_id")

    if parent_converter_id is None:
        return document

    direct_child_tables = get_direct_child_tables(table_name, intermediate_data)

    for child_table in direct_child_tables:
        child_records = intermediate_data.get(child_table, [])
        matching_children = []

        for child_record in child_records:
            if child_record.get("__parent_id") == parent_converter_id:
                if is_simple_value_record(child_record):
                    matching_children.append(child_record.get("value"))
                else:
                    child_document = build_document_from_record(
                        child_table,
                        child_record,
                        intermediate_data
                    )
                    matching_children.append(child_document)

        if matching_children:
            field_name = get_field_name_from_child_table(table_name, child_table)
            document[field_name] = matching_children

    return document


def rebuild_mongo_documents_from_relations(intermediate_data):
    rebuilt_data = {}
    root_tables = get_root_tables(intermediate_data)

    for root_table in root_tables:
        records = intermediate_data.get(root_table, [])
        documents = []

        for record in records:
            document = build_document_from_record(
                root_table,
                record,
                intermediate_data
            )

            document = restore_mongo_value(document)
            document = restore_object_id(document)

            documents.append(document)

        rebuilt_data[root_table] = documents

    return rebuilt_data


def is_postgres_foreign_key_data(intermediate_data):
    metadata = get_postgres_schema_metadata(intermediate_data)
    foreign_keys = metadata.get("foreign_keys", [])

    return len(foreign_keys) > 0


def remove_columns_from_document(record, columns_to_remove):
    document = {}

    for key, value in record.items():
        if key in columns_to_remove:
            continue

        if key in ["__converter_id", "__parent_id"]:
            continue

        document[key] = value

    return document


def get_child_relations(parent_table, foreign_keys):
    relations = []

    for relation in foreign_keys:
        if relation["parent_table"] == parent_table:
            relations.append(relation)

    return relations


def get_parent_tables_from_foreign_keys(foreign_keys):
    parent_tables = set()

    for relation in foreign_keys:
        parent_tables.add(relation["parent_table"])

    return parent_tables


def get_child_tables_from_foreign_keys(foreign_keys):
    child_tables = set()

    for relation in foreign_keys:
        child_tables.add(relation["child_table"])

    return child_tables


def get_root_tables_from_foreign_keys(tables, foreign_keys):
    parent_tables = get_parent_tables_from_foreign_keys(foreign_keys)
    child_tables = get_child_tables_from_foreign_keys(foreign_keys)

    root_tables = []

    for table_name in tables.keys():
        if table_name in parent_tables and table_name not in child_tables:
            root_tables.append(table_name)

    if root_tables:
        return root_tables

    for table_name in tables.keys():
        if table_name not in child_tables:
            root_tables.append(table_name)

    if root_tables:
        return root_tables

    return list(tables.keys())


def get_field_name_for_relation(parent_table, child_table):
    prefix = parent_table + "_"

    if child_table.startswith(prefix):
        return child_table[len(prefix):]

    return child_table


def build_document_from_foreign_keys(
    table_name,
    record,
    tables,
    foreign_keys,
    visited=None
):
    if visited is None:
        visited = set()

    record_identity = (
        table_name,
        str(record)
    )

    if record_identity in visited:
        return remove_columns_from_document(record, set())

    visited.add(record_identity)

    columns_to_remove = set()

    for relation in foreign_keys:
        if relation["child_table"] == table_name:
            columns_to_remove.add(relation["child_column"])

    document = remove_columns_from_document(
        record,
        columns_to_remove
    )

    child_relations = get_child_relations(
        table_name,
        foreign_keys
    )

    for relation in child_relations:
        child_table = relation["child_table"]
        child_column = relation["child_column"]
        parent_column = relation["parent_column"]

        parent_value = record.get(parent_column)
        child_records = tables.get(child_table, [])

        nested_items = []

        for child_record in child_records:
            child_value = child_record.get(child_column)

            if values_are_equal(child_value, parent_value):
                child_document = build_document_from_foreign_keys(
                    child_table,
                    child_record,
                    tables,
                    foreign_keys,
                    visited.copy()
                )

                nested_items.append(child_document)

        if nested_items:
            field_name = get_field_name_for_relation(
                table_name,
                child_table
            )

            document[field_name] = nested_items

    return document


def rebuild_mongo_documents_from_foreign_keys(intermediate_data):
    metadata = get_postgres_schema_metadata(intermediate_data)
    foreign_keys = metadata.get("foreign_keys", [])
    selected_table = metadata.get("selected_table")

    tables = get_real_tables_from_intermediate(intermediate_data)

    if not foreign_keys:
        return tables

    if selected_table and selected_table in tables:
        root_tables = [selected_table]
    else:
        root_tables = get_root_tables_from_foreign_keys(
            tables,
            foreign_keys
        )

    rebuilt_data = {}

    for root_table in root_tables:
        records = tables.get(root_table, [])
        documents = []

        for record in records:
            document = build_document_from_foreign_keys(
                root_table,
                record,
                tables,
                foreign_keys
            )

            document = restore_mongo_value(document)
            document = restore_object_id(document)

            documents.append(document)

        rebuilt_data[root_table] = documents

    return rebuilt_data


def get_reference_id_from_record(record):
    if "_id" in record:
        return record["_id"]

    if "id" in record:
        return record["id"]

    if "__converter_id" in record:
        return record["__converter_id"]

    return None


def get_reference_field_name(child_table):
    return f"{child_table}_ids"


def rebuild_mongo_documents_as_references(intermediate_data):
    metadata = get_postgres_schema_metadata(intermediate_data)
    foreign_keys = metadata.get("foreign_keys", [])

    tables = get_real_tables_from_intermediate(intermediate_data)

    rebuilt_data = {}

    for table_name, records in tables.items():
        documents = []

        for record in records:
            document = dict(record)
            document = restore_mongo_value(document)
            document = restore_object_id(document)
            documents.append(document)

        rebuilt_data[table_name] = documents

    if not foreign_keys:
        return rebuilt_data

    for relation in foreign_keys:
        parent_table = relation["parent_table"]
        parent_column = relation["parent_column"]
        child_table = relation["child_table"]
        child_column = relation["child_column"]

        parent_records = rebuilt_data.get(parent_table, [])
        child_records = rebuilt_data.get(child_table, [])

        reference_field = get_reference_field_name(child_table)

        for parent_record in parent_records:
            parent_value = parent_record.get(parent_column)
            related_child_ids = []

            for child_record in child_records:
                child_value = child_record.get(child_column)

                if values_are_equal(parent_value, child_value):
                    child_reference_id = get_reference_id_from_record(child_record)

                    if child_reference_id is not None:
                        related_child_ids.append(child_reference_id)

            if related_child_ids:
                parent_record[reference_field] = related_child_ids

    return rebuilt_data


def write_plain_intermediate_to_mongo(db, intermediate_data):
    for collection_name, records in intermediate_data.items():
        if collection_name.startswith("__"):
            continue

        collection = db[collection_name]
        collection.delete_many({})

        documents_to_insert = []

        for record in records:
            document = dict(record)
            document = restore_mongo_value(document)
            document = restore_object_id(document)
            documents_to_insert.append(document)

        if documents_to_insert:
            collection.insert_many(documents_to_insert)


def write_intermediate_to_mongo(
    host,
    port,
    database,
    intermediate_data,
    mongo_write_mode="Embedding"
):
    client = None

    try:
        client = get_mongo_client(host, port)
        db = client[database]

        selected_mode = str(mongo_write_mode).strip().lower()

        if selected_mode == "referencing":
            rebuilt_data = rebuild_mongo_documents_as_references(
                intermediate_data
            )

            write_plain_intermediate_to_mongo(db, rebuilt_data)
            return

        if is_postgres_foreign_key_data(intermediate_data):
            rebuilt_data = rebuild_mongo_documents_from_foreign_keys(
                intermediate_data
            )

            write_plain_intermediate_to_mongo(db, rebuilt_data)
            return

        if is_converter_relation_data(intermediate_data):
            rebuilt_data = rebuild_mongo_documents_from_relations(
                intermediate_data
            )

            write_plain_intermediate_to_mongo(db, rebuilt_data)
            return

        clean_data = get_real_tables_from_intermediate(intermediate_data)
        write_plain_intermediate_to_mongo(db, clean_data)

    finally:
        if client is not None:
            client.close()


def get_mongo_database_size_mb(host, port, database):
    client = None

    try:
        client = get_mongo_client(host, port)
        db = client[database]

        stats = db.command("dbStats")
        data_size = stats.get("dataSize", 0)

        return data_size / (1024 * 1024)

    except Exception:
        return 0.0

    finally:
        if client is not None:
            client.close()


def measure_mongo_read_ms(host, port, database, collection_name=None, repeats=5):
    client = None

    try:
        client = get_mongo_client(host, port)
        db = client[database]

        if collection_name is None:
            collections = db.list_collection_names()

            if not collections:
                return 0.0

            collection_name = collections[0]

        collection = db[collection_name]

        total_time = 0.0
        successful_reads = 0

        for _ in range(repeats):
            start_time = time.perf_counter()
            collection.find_one()
            end_time = time.perf_counter()

            total_time += end_time - start_time
            successful_reads += 1

        if successful_reads == 0:
            return 0.0

        average_time_s = total_time / successful_reads

        return average_time_s * 1000

    except Exception:
        return 0.0

    finally:
        if client is not None:
            client.close()