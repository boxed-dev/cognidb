class QueryExecutor:
    def __init__(self, db_driver):
        self.db_driver = db_driver

    def execute_sql(self, sql_query):
        return self.db_driver.execute_query(sql_query)
