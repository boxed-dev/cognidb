class BaseDB:
    def connect(self):
        raise NotImplementedError("Connect method not implemented.")

    def fetch_schema(self):
        raise NotImplementedError("Fetch schema method not implemented.")

    def execute_query(self, query):
        raise NotImplementedError("Execute query method not implemented.")
