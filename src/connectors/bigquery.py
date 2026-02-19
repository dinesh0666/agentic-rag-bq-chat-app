"""BigQuery connector with schema introspection and query generation."""

import os
from typing import List, Dict, Any, Optional
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account


class BigQueryConnector:
    """Connector for BigQuery with schema introspection."""
    
    def __init__(
        self,
        project_id: Optional[str] = None,
        credentials_path: Optional[str] = None,
        dataset_id: Optional[str] = None,
        data_project_id: Optional[str] = None
    ):
        """
        Initialize BigQuery connector.
        
        Args:
            project_id: Billing project ID (where queries are executed and billed)
            credentials_path: Path to service account JSON
            dataset_id: Dataset name (e.g., "iowa_liquor_sales")
            data_project_id: Project containing the dataset (defaults to project_id)
                            Use "bigquery-public-data" for public datasets
        """
        self.project_id = project_id or os.getenv("BIGQUERY_PROJECT_ID", "bigquery-public-data")
        self.dataset_id = dataset_id or os.getenv("BIGQUERY_DATASET")
        
        # For public datasets, data lives in bigquery-public-data
        # but queries are billed to your project
        if self.dataset_id == "iowa_liquor_sales":
            self.data_project_id = "bigquery-public-data"
        else:
            self.data_project_id = data_project_id or self.project_id
        
        credentials_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        
        # Initialize client - will use default credentials if available
        try:
            # Try with credentials if provided and file exists
            if credentials_path and credentials_path != "" and os.path.exists(credentials_path):
                try:
                    credentials = service_account.Credentials.from_service_account_file(
                        credentials_path
                    )
                    self.client = bigquery.Client(
                        credentials=credentials,
                        project=self.project_id
                    )
                except Exception as e:
                    print(f"Warning: Could not load credentials from {credentials_path}: {e}")
                    self.client = bigquery.Client(project=self.project_id)
            else:
                # Try default credentials (works if gcloud auth is set up)
                self.client = bigquery.Client(project=self.project_id)
        except Exception as e:
            # If no credentials at all, raise helpful error
            raise Exception(
                f"BigQuery authentication failed: {str(e)}\n\n"
                "To fix this, you have 3 options:\n"
                "1. Run: gcloud auth application-default login\n"
                "2. Set GOOGLE_APPLICATION_CREDENTIALS to your service account JSON file\n"
                "3. For testing, you can install gcloud SDK: https://cloud.google.com/sdk/docs/install"
            )
    
    def get_tables(self) -> List[str]:
        """Get list of tables in the dataset."""
        tables = self.client.list_tables(f"{self.data_project_id}.{self.dataset_id}")
        return [table.table_id for table in tables]
    
    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Get schema information for a table."""
        table_ref = f"{self.data_project_id}.{self.dataset_id}.{table_name}"
        table = self.client.get_table(table_ref)
        
        schema_info = {
            "table_name": table_name,
            "description": table.description or "",
            "columns": []
        }
        
        for field in table.schema:
            column_info = {
                "name": field.name,
                "type": field.field_type,
                "mode": field.mode,
                "description": field.description or ""
            }
            schema_info["columns"].append(column_info)
        
        return schema_info
    
    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """Get schema information for all tables."""
        tables = self.get_tables()
        return [self.get_table_schema(table) for table in tables]
    
    def execute_query(self, query: str) -> pd.DataFrame:
        """Execute a BigQuery SQL query and return results as DataFrame."""
        try:
            query_job = self.client.query(query)
            return query_job.to_dataframe()
        except Exception as e:
            raise Exception(f"Query execution failed: {str(e)}")
    
    def get_sample_data(self, table_name: str, limit: int = 5) -> pd.DataFrame:
        """Get sample data from a table."""
        query = f"""
        SELECT *
        FROM `{self.data_project_id}.{self.dataset_id}.{table_name}`
        LIMIT {limit}
        """
        return self.execute_query(query)
    
    def validate_query(self, query: str) -> Dict[str, Any]:
        """Validate a query without executing it."""
        job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        
        try:
            query_job = self.client.query(query, job_config=job_config)
            return {
                "valid": True,
                "bytes_processed": query_job.total_bytes_processed,
                "message": "Query is valid"
            }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
                "message": "Query validation failed"
            }
    
    def get_table_stats(self, table_name: str) -> Dict[str, Any]:
        """Get statistics about a table."""
        query = f"""
        SELECT
            COUNT(*) as row_count,
            COUNT(DISTINCT *) as distinct_rows
        FROM `{self.data_project_id}.{self.dataset_id}.{table_name}`
        """
        
        try:
            result = self.execute_query(query)
            table_ref = f"{self.data_project_id}.{self.dataset_id}.{table_name}"
            table = self.client.get_table(table_ref)
            
            return {
                "row_count": int(result['row_count'].iloc[0]) if not result.empty else 0,
                "size_mb": table.num_bytes / (1024 * 1024),
                "created": table.created,
                "modified": table.modified
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_schema_context(self) -> str:
        """Get full schema as a formatted string (legacy helper — prefer SchemaVectorStore for RAG)."""
        schemas = self.get_all_schemas()
        context_parts = []
        
        for schema in schemas:
            table_info = f"\nTable: {schema['table_name']}"
            if schema.get('description'):
                table_info += f"\nDescription: {schema['description']}"
            
            table_info += "\nColumns:"
            for col in schema['columns']:
                col_info = f"\n  - {col['name']} ({col['type']})"
                if col.get('description'):
                    col_info += f": {col['description']}"
                table_info += col_info
            
            context_parts.append(table_info)
        
        return "\n".join(context_parts)
