import logging
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from typing import Dict, Any
from .base_db import BaseDB

logger = logging.getLogger(__name__)

class AwsDB(BaseDB):
    """
    AWS DynamoDB driver that provides connection management,
    table listing as schema, and basic query execution.
    """
    def __init__(self, region_name: str, access_key: str, secret_key: str):
        self.region_name = region_name
        self.access_key = access_key
        self.secret_key = secret_key
        self.dynamodb = None

    def connect(self):
        """
        Establishes a connection to AWS DynamoDB.
        """
        try:
            self.dynamodb = boto3.resource(
                'dynamodb',
                region_name=self.region_name,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key
            )
            logger.info("AWS DynamoDB connection established successfully.")
            return self.dynamodb
        except (BotoCoreError, ClientError) as err:
            logger.error("Failed to connect to AWS DynamoDB: %s", err)
            raise Exception(f"AWS DynamoDB connection failed: {err}")

    def fetch_schema(self) -> Dict[str, Any]:
        """
        Retrieves the list of DynamoDB tables.
        """
        if self.dynamodb is None:
            self.connect()

        try:
            client = boto3.client(
                'dynamodb',
                region_name=self.region_name,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key
            )
            response = client.list_tables()
            tables = response.get("TableNames", [])
            logger.info("AWS DynamoDB tables fetched successfully.")
            # Optionally, you could describe each table for more schema info.
            return {"tables": tables}
        except (BotoCoreError, ClientError) as err:
            logger.error("Error fetching AWS DynamoDB tables: %s", err)
            raise Exception(f"Error fetching DynamoDB schema: {err}")

    def execute_query(self, query: Dict[str, Any]) -> Any:
        """
        Executes a DynamoDB operation.
        The query dict should contain:
            - 'table': Name of the table.
            - 'operation': Operation type (e.g., "get_item", "put_item", "query").
            - Additional keys needed for the operation.
        Example for get_item:
            {
                "table": "users",
                "operation": "get_item",
                "key": {"user_id": {"S": "123"}}
            }
        """
        if self.dynamodb is None:
            self.connect()

        try:
            table_name = query.get("table")
            operation = query.get("operation")
            table = self.dynamodb.Table(table_name)

            if operation == "get_item":
                key = query.get("key")
                response = table.get_item(Key=key)
                return response.get("Item")
            elif operation == "put_item":
                item = query.get("item")
                response = table.put_item(Item=item)
                return response
            elif operation == "query":
                key_condition = query.get("KeyConditionExpression")
                # Note: This assumes key_condition is a boto3 condition expression.
                response = table.query(KeyConditionExpression=key_condition)
                return response.get("Items")
            else:
                raise Exception(f"Unsupported DynamoDB operation: {operation}")
        except (BotoCoreError, ClientError) as err:
            logger.error("Error executing AWS DynamoDB operation: %s", err)
            raise Exception(f"DynamoDB query execution failed: {err}")