import logging
from pymongo import MongoClient, errors
from typing import Dict, List, Any, Optional
from .base_db import BaseDB

logger = logging.getLogger(__name__)

class MongoDB(BaseDB):
    """
    MongoDB driver that provides connection management,
    basic collection schema fetching, and rudimentary query execution.
    """
    def __init__(self, connection_uri: str, dbname: str):
        self.connection_uri = connection_uri
        self.dbname = dbname
        self.client: Optional[MongoClient] = None
        self.db = None

    def connect(self) -> MongoClient:
        """
        Establishes a connection to the MongoDB database.
        """
        try:
            self.client = MongoClient(self.connection_uri)
            self.db = self.client[self.dbname]
            logger.info("MongoDB connection established successfully.")
            return self.client
        except errors.PyMongoError as err:
            logger.error("Failed to connect to MongoDB: %s", err)
            raise Exception(f"MongoDB connection failed: {err}")

    def fetch_schema(self) -> Dict[str, List[str]]:
        """
        Retrieves the database schema by fetching collection names and sample keys.
        For each collection, it fetches one document and returns its keys as schema.
        """
        if self.client is None:
            self.connect()

        schema: Dict[str, List[str]] = {}
        try:
            collections = self.db.list_collection_names()
            for coll in collections:
                collection = self.db[coll]
                sample = collection.find_one()
                if sample:
                    schema[coll] = list(sample.keys())
                else:
                    schema[coll] = []
            logger.info("MongoDB schema fetched successfully.")
            return schema
        except errors.PyMongoError as err:
            logger.error("Error fetching MongoDB schema: %s", err)
            raise Exception(f"Error fetching MongoDB schema: {err}")

    def execute_query(self, query: Dict[str, Any]) -> Any:
        """
        Executes a MongoDB operation.
        The query dict should contain:
            - 'collection': Name of the collection.
            - 'operation': Operation type (e.g., "find", "insert_one", "update_one", "delete_one").
            - Additional keys needed for the operation.
        Example for find:
            {
                "collection": "users",
                "operation": "find",
                "filter": {"age": {"$gt": 30}}
            }
        """
        if self.client is None:
            self.connect()

        try:
            coll_name = query.get("collection")
            operation = query.get("operation")
            collection = self.db[coll_name]

            if operation == "find":
                filter_query = query.get("filter", {})
                result = list(collection.find(filter_query))
                return result
            elif operation == "insert_one":
                document = query.get("document")
                result = collection.insert_one(document)
                return {"inserted_id": str(result.inserted_id)}
            elif operation == "update_one":
                filter_query = query.get("filter", {})
                update_query = query.get("update", {})
                result = collection.update_one(filter_query, update_query)
                return {"matched_count": result.matched_count, "modified_count": result.modified_count}
            elif operation == "delete_one":
                filter_query = query.get("filter", {})
                result = collection.delete_one(filter_query)
                return {"deleted_count": result.deleted_count}
            else:
                raise Exception(f"Unsupported MongoDB operation: {operation}")
        except errors.PyMongoError as err:
            logger.error("Error executing MongoDB operation: %s", err)
            raise Exception(f"MongoDB query execution failed: {err}")