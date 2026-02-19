"""
Example Usage Script - Demonstrates programmatic usage of Agentic RAG

This script shows how to use the Agentic RAG system programmatically
outside of the Streamlit UI.
"""

import os
from dotenv import load_dotenv
from src.agents import AgenticRAG
from src.config import ConfigManager
from src.connectors import BigQueryConnector
import pandas as pd

# Load environment variables
load_dotenv()

def example_basic_usage():
    """Example 1: Basic usage with default configuration."""
    print("=" * 80)
    print("Example 1: Basic Usage")
    print("=" * 80)
    
    # Initialize components
    config_manager = ConfigManager()
    bq_connector = BigQueryConnector()
    agent = AgenticRAG(
        config_manager=config_manager,
        bq_connector=bq_connector
    )
    
    # Process a query
    query = "Show me the top 5 customers by revenue"
    result = agent.process_query(query)
    
    print(f"\nQuery: {query}")
    print(f"\nResponse: {result['response']}")
    
    if result.get('sql_query'):
        print(f"\nGenerated SQL:\n{result['sql_query']}")
    
    if result.get('data') is not None:
        print(f"\nData Shape: {result['data'].shape}")
        print(f"\nData Preview:\n{result['data'].head()}")


def example_with_custom_config():
    """Example 2: Using a custom configuration file."""
    print("\n" + "=" * 80)
    print("Example 2: Custom Configuration")
    print("=" * 80)
    
    # Load specific config
    config_manager = ConfigManager(config_path="./configs/ecommerce_config.yaml")
    bq_connector = BigQueryConnector()
    agent = AgenticRAG(
        config_manager=config_manager,
        bq_connector=bq_connector,
        llm_provider="gemini"  # Explicitly specify provider
    )
    
    # Use business calculation
    query = "Calculate the customer lifetime value"
    result = agent.process_query(query)
    
    print(f"\nQuery: {query}")
    print(f"\nResponse: {result['response']}")
    
    if result.get('calculation_result'):
        print(f"\nCalculation Result: {result['calculation_result']}")


def example_batch_queries():
    """Example 3: Process multiple queries in batch."""
    print("\n" + "=" * 80)
    print("Example 3: Batch Query Processing")
    print("=" * 80)
    
    # Initialize once
    config_manager = ConfigManager()
    bq_connector = BigQueryConnector()
    agent = AgenticRAG(config_manager, bq_connector)
    
    # Define multiple queries
    queries = [
        "Show me total revenue",
        "What are the top 3 products?",
        "Calculate average order value"
    ]
    
    results = []
    for query in queries:
        print(f"\nProcessing: {query}")
        result = agent.process_query(query)
        results.append({
            'query': query,
            'response': result['response'],
            'has_data': result.get('data') is not None and not result['data'].empty
        })
        print(f"✓ Complete")
    
    # Summary
    print("\n" + "-" * 80)
    print("Batch Processing Summary:")
    print("-" * 80)
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['query']}")
        print(f"   Has Data: {r['has_data']}")
        print(f"   Response: {r['response'][:100]}...")


def example_direct_components():
    """Example 4: Using components directly without the agent."""
    print("\n" + "=" * 80)
    print("Example 4: Direct Component Usage")
    print("=" * 80)
    
    # Direct BigQuery access
    bq_connector = BigQueryConnector()
    
    # Get schema information
    print("\n1. Schema Information:")
    schemas = bq_connector.get_all_schemas()
    for schema in schemas:
        print(f"   Table: {schema['table_name']}")
        print(f"   Columns: {len(schema['columns'])}")
    
    # Execute direct SQL
    print("\n2. Direct SQL Execution:")
    sql = """
    SELECT COUNT(*) as total_rows
    FROM `{}.{}.customers`
    LIMIT 1
    """.format(
        os.getenv('BIGQUERY_PROJECT_ID'),
        os.getenv('BIGQUERY_DATASET')
    )
    
    try:
        df = bq_connector.execute_query(sql)
        print(f"   Result: {df.iloc[0]['total_rows']} rows in customers table")
    except Exception as e:
        print(f"   Note: Adjust table name for your dataset - {str(e)}")
    
    # Use visualization directly
    print("\n3. Direct Visualization:")
    from src.visualization import DataVisualizer
    
    visualizer = DataVisualizer()
    sample_data = pd.DataFrame({
        'category': ['A', 'B', 'C', 'D'],
        'value': [10, 25, 15, 30]
    })
    
    fig = visualizer.auto_visualize(sample_data)
    print(f"   Created chart with {len(fig.data)} traces")
    # In a notebook, you would: fig.show()
    
    # Use business calculations directly
    print("\n4. Direct Calculation:")
    config_manager = ConfigManager()
    try:
        result = config_manager.evaluate_calculation(
            "average_order_value",
            {"total_revenue": 100000, "total_orders": 500}
        )
        print(f"   Average Order Value: ${result}")
    except ValueError as e:
        print(f"   Note: Configure calculation in your config file")


def example_error_handling():
    """Example 5: Proper error handling."""
    print("\n" + "=" * 80)
    print("Example 5: Error Handling")
    print("=" * 80)
    
    try:
        config_manager = ConfigManager()
        bq_connector = BigQueryConnector()
        agent = AgenticRAG(config_manager, bq_connector)
        
        # This might fail if table doesn't exist
        result = agent.process_query("Show data from nonexistent_table")
        print(f"\nResponse: {result['response']}")
        
    except Exception as e:
        print(f"\nError occurred: {type(e).__name__}")
        print(f"Message: {str(e)}")
        print("\nTip: Check your configuration and BigQuery setup")


def example_context_building():
    """Example 6: Building rich context for the agent."""
    print("\n" + "=" * 80)
    print("Example 6: Context Building")
    print("=" * 80)
    
    config_manager = ConfigManager()
    bq_connector = BigQueryConnector()
    
    # Get various context information
    print("\n1. Domain Context:")
    domain_context = config_manager.get_domain_context()
    print(f"   {domain_context[:200]}..." if domain_context else "   Not configured")
    
    print("\n2. Calculation Context:")
    calc_context = config_manager.get_calculation_context()
    print(f"   {calc_context[:200]}...")
    
    print("\n3. Schema Context:")
    schema_context = bq_connector.get_schema_context()
    print(f"   {schema_context[:200]}...")
    
    print("\n4. Table Statistics:")
    tables = bq_connector.get_tables()
    for table in tables[:2]:  # First 2 tables
        try:
            stats = bq_connector.get_table_stats(table)
            print(f"   {table}: {stats.get('row_count', 'N/A')} rows")
        except:
            print(f"   {table}: Stats unavailable")


def example_custom_llm():
    """Example 7: Using different LLM providers."""
    print("\n" + "=" * 80)
    print("Example 7: Custom LLM Provider")
    print("=" * 80)
    
    config_manager = ConfigManager()
    bq_connector = BigQueryConnector()
    
    # Try with Gemini
    print("\n1. Using Gemini:")
    try:
        agent_gemini = AgenticRAG(
            config_manager, bq_connector, llm_provider="gemini"
        )
        result = agent_gemini.process_query("What is 2+2?")
        print(f"   Response: {result['response']}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Try with OpenRouter
    print("\n2. Using OpenRouter:")
    try:
        agent_openrouter = AgenticRAG(
            config_manager, bq_connector, llm_provider="openrouter"
        )
        result = agent_openrouter.process_query("What is 3+3?")
        print(f"   Response: {result['response']}")
    except Exception as e:
        print(f"   Error: {e}")


def main():
    """Run all examples."""
    print("\n")
    print("🤖 Agentic RAG - Example Usage Demonstrations")
    print("=" * 80)
    print("\nNote: Make sure you have:")
    print("- Configured .env file with API keys")
    print("- Set up BigQuery credentials")
    print("- Created a client config file")
    print("\n")
    
    try:
        # Run examples
        # example_basic_usage()
        # example_with_custom_config()
        # example_batch_queries()
        example_direct_components()
        # example_error_handling()
        # example_context_building()
        # example_custom_llm()
        
        print("\n" + "=" * 80)
        print("✨ Examples completed!")
        print("=" * 80)
        print("\nTip: Uncomment other examples in main() to try them")
        print("Tip: Modify the queries to match your data")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure all prerequisites are configured correctly")


if __name__ == "__main__":
    main()
