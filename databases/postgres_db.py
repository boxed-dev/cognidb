import psycopg2
from .base_db import BaseDB

class PostgresDB(BaseDB):
    def __init__(self, host, port, dbname, user, password):
        self.connection_params = {
            'host': host,
            'port': port,
            'dbname': dbname,
            'user': user,
            'password': password
        }
        self.conn = None

    def connect(self):
        self.conn = psycopg2.connect(**self.connection_params)
        return self.conn

    def fetch_schema(self):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
        )
        tables = cursor.fetchall()
        schema = {}
        for table in tables:
            cursor.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = %s;", (table[0],)
            )
            columns = cursor.fetchall()
            schema[table[0]] = [col[0] for col in columns]
        return schema

    def execute_query(self, query):
        cursor = self.conn.cursor()
        cursor.execute(query)
        if cursor.description:
            return cursor.fetchall()
        self.conn.commit()
        return None
