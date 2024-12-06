class SchemaFetcher:
    def __init__(self, db_driver):
        self.db_driver = db_driver

    def fetch_schema(self):
        return self.db_driver.fetch_schema()
