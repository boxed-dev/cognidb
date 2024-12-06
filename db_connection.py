class DBConnection:
    def __init__(self, db_driver):
        self.db_driver = db_driver

    def connect(self):
        return self.db_driver.connect()
