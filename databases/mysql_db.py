import mysql.connector
from .base_db import BaseDB

class MySQLDB(BaseDB):
    def __init__(self, host, port, database, user, password, ssl_required=False):
        self.connection_params = {
            'host': host,
            'port': port,
            'database': database,
            'user': user,
            'password': password
        }
        
        if ssl_required:
            self.connection_params.update({
                'ssl_disabled': False,
                'ssl_verify_identity': False,
                'ssl_verify_cert': False
            })
        
        self.conn = None

    def connect(self):
        try:
            self.conn = mysql.connector.connect(**self.connection_params)
            return self.conn
        except mysql.connector.Error as err:
            raise Exception(f"Failed to connect to MySQL: {err}")

    def fetch_schema(self):
        cursor = self.conn.cursor()
        cursor.execute("SHOW TABLES;")
        tables = cursor.fetchall()
        schema = {}
        for table in tables:
            cursor.execute(f"DESCRIBE {table[0]};")
            columns = cursor.fetchall()
            schema[table[0]] = [col[0] for col in columns]
        # print(schema)
        return schema

    def execute_query(self, query):
        cursor = self.conn.cursor()
        results = []
        
        queries = [q.strip() for q in query.split(';') if q.strip()]
        
        for single_query in queries:
            cursor.execute(single_query)
            if cursor.description:
                results.append(cursor.fetchall())
            else:
                self.conn.commit()
        
        cursor.close()
        return results[0] if len(results) == 1 else results
