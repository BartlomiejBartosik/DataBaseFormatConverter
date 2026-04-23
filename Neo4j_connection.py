from neo4j import GraphDatabase

URI = "bolt://localhost:7687"
USER = "neo4j"
PASSWORD = "12345678"

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

with driver.session(database="test") as session:
    result = session.run("RETURN 'Połączono!' AS msg")
    for record in result:
        print(record["msg"])

with driver.session(database="test") as session:
    result = session.run("""
        MATCH (p:Person)
        RETURN p.name AS name, p.surname AS surname
    """)

    for record in result:
        print(record["name"], record["surname"])

driver.close()