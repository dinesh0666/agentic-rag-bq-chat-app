"""Simple CLI tool for testing the agentic RAG system."""

import argparse
import sys
from dotenv import load_dotenv

from src.agents import AgenticRAG
from src.config import ConfigManager
from src.connectors import BigQueryConnector

load_dotenv()


def main():
    """CLI main function."""
    parser = argparse.ArgumentParser(description="Agentic RAG CLI")
    parser.add_argument("query", nargs="*", help="Query to process")
    parser.add_argument("--config", help="Path to client config file")
    parser.add_argument("--provider", help="LLM provider (gemini/openrouter)")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    
    args = parser.parse_args()
    
    try:
        # Initialize components
        print("🔧 Initializing system...")
        config_manager = ConfigManager(config_path=args.config)
        bq_connector = BigQueryConnector()
        agent = AgenticRAG(
            config_manager=config_manager,
            bq_connector=bq_connector,
            llm_provider=args.provider
        )
        print("✅ System initialized\n")
        
        if args.interactive:
            interactive_mode(agent)
        else:
            # Process single query
            query = " ".join(args.query)
            if not query:
                parser.print_help()
                return
            
            process_query(agent, query)
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)


def process_query(agent: AgenticRAG, query: str):
    """Process a single query."""
    print(f"❓ Query: {query}\n")
    print("🤔 Processing...\n")
    
    result = agent.process_query(query)
    
    print("=" * 80)
    print("📝 Response:")
    print("=" * 80)
    print(result["response"])
    print()
    
    if result.get("sql_query"):
        print("=" * 80)
        print("📊 SQL Query:")
        print("=" * 80)
        print(result["sql_query"])
        print()
    
    if result.get("data") is not None and not result["data"].empty:
        print("=" * 80)
        print("📈 Data:")
        print("=" * 80)
        print(result["data"].to_string())
        print()
    
    if result.get("calculation_result") is not None:
        print("=" * 80)
        print("🧮 Calculation Result:")
        print("=" * 80)
        print(result["calculation_result"])
        print()


def interactive_mode(agent: AgenticRAG):
    """Interactive CLI mode."""
    print("=" * 80)
    print("🤖 Interactive Agentic RAG")
    print("=" * 80)
    print("Type your queries (or 'exit' to quit)\n")
    
    while True:
        try:
            query = input("You: ").strip()
            
            if not query:
                continue
            
            if query.lower() in ["exit", "quit", "q"]:
                print("\n👋 Goodbye!")
                break
            
            print()
            process_query(agent, query)
            print()
        
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}\n")


if __name__ == "__main__":
    main()
