import openai
from openai import OpenAI

class LLMQueryGenerator:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)

    def generate_sql(self, user_input, schema):
        prompt = f"""Given the database schema: {schema}
        Generate ONLY the SQL query (no explanations) for: {user_input}
        The response should contain nothing but the SQL query itself.
        For example, if asked to show tables, respond with exactly: 'SHOW TABLES;'"""
        # print(prompt)
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "system",
                "content": "You are a MYSQL query generator. Respond with ONLY the SQL query, no explanations or additional text."
            },
            {
                "role": "user",
                "content": prompt
            }],
            temperature=0.2,
            max_tokens=1500
        )
        sql_query = response.choices[0].message.content.strip()
        # print(sql_query)
        # Basic validation to ensure it's a SQL query
        if not any(sql_query.lower().startswith(keyword) for keyword in ['select', 'show', 'describe', 'insert', 'update', 'delete', 'create', 'alter', 'drop']):
            return "SHOW TABLES;"  # Fallback for showing tables
        
        return sql_query
