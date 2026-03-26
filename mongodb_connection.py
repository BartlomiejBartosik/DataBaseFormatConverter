from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")

db = client["db_converter"]

kolekcja = db["osoby"]

for osoba in kolekcja.find():
    print(osoba)