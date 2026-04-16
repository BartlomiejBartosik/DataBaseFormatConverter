from pymongo import MongoClient


def test_mongo_connection(host, port, database):
    uri = f"mongodb://{host}:{port}/"
    client = None

    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
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


def get_mongo_data(host, port, database, collection_name="osoby"):
    uri = f"mongodb://{host}:{port}/"
    client = None

    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        db = client[database]
        collection = db[collection_name]

        data = []
        for document in collection.find():
            document["_id"] = str(document["_id"])
            data.append(document)

        return data
    finally:
        if client is not None:
            client.close()