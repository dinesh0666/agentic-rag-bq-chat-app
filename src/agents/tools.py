"""
LangChain tools for the ReAct agentic RAG orchestrator.

Each tool wraps one concrete capability. The LLM decides which tools to call
and in what order — no hard-coded pipelines.
"""

import json
import re
from typing import Any, Dict, Optional

from langchain_core.tools import tool


# ---------------------------------------------------------------------------
# Factory — returns all tools bound to runtime dependencies
# ---------------------------------------------------------------------------

def build_tools(
    bq_connector,
    schema_store,
    chat_history=None,
    config_manager=None,
    llm=None,
):
    """
    Build all agent tools with their dependencies injected via closure.
    
    Args:
        bq_connector:   BigQueryConnector instance
        schema_store:   SchemaVectorStore instance  
        chat_history:   ChatHistoryManager (optional, for memory search)
        config_manager: ConfigManager (optional, for calculations)
        llm:            LLM instance used for SQL self-correction
    
    Returns:
        List of langchain Tool objects
    """

    # ------------------------------------------------------------------
    # Tool 1 — Schema search (the RAG step)
    # ------------------------------------------------------------------
    @tool
    def search_schema(query: str) -> str:
        """
        Search the schema knowledge base for relevant tables, columns, and business rules.
        
        Call this FIRST before writing any SQL. Provide a natural language description
        of what data you need. Returns the most relevant schema sections.
        
        Args:
            query: Natural language description of data needed (e.g. "monthly revenue by product")
        """
        if not schema_store.is_ready:
            return "Schema store not initialised yet — use list_tables to discover tables."
        context = schema_store.get_relevant_schema_context(query, k=10)
        return context

    # ------------------------------------------------------------------
    # Tool 2 — List all tables
    # ------------------------------------------------------------------
    @tool
    def list_tables() -> str:
        """
        List all available BigQuery tables in the dataset.
        
        Call this when you're unsure which tables exist or when schema_search
        doesn't return useful results.
        """
        try:
            tables = bq_connector.get_tables()
            if not tables:
                return "No tables found in the dataset."
            return "Available tables:\n" + "\n".join(f"  - {t}" for t in tables)
        except Exception as e:
            return f"Error listing tables: {e}"

    # ------------------------------------------------------------------
    # Tool 3 — Execute SQL (with self-correction loop)
    # ------------------------------------------------------------------
    @tool
    def execute_sql(sql: str) -> str:
        """
        Execute a GoogleSQL query on BigQuery and return the results as JSON.
        
        If the query has a syntax or schema error the tool will attempt to
        auto-correct the SQL up to 3 times using the LLM before giving up.
        Always validate column names against search_schema results first.
        
        Args:
            sql: Valid GoogleSQL (BigQuery) SELECT statement
        """
        sql = sql.strip()
        # Strip markdown code fences if model wraps SQL
        sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.I)
        sql = re.sub(r"\s*```$", "", sql)
        sql = sql.strip()

        last_error = None
        for attempt in range(3):
            try:
                df = bq_connector.execute_query(sql)
                if df is None or df.empty:
                    return "Query returned no results."
                result = {
                    "columns": df.columns.tolist(),
                    "rows": df.head(200).to_dict(orient="records"),
                    "row_count": len(df),
                    "sql_executed": sql,
                }
                return json.dumps(result, default=str)
            except Exception as e:
                last_error = str(e)
                if attempt < 2 and llm is not None:
                    # Ask the LLM to fix the SQL
                    fix_prompt = (
                        f"The following BigQuery SQL raised an error:\n\n"
                        f"```sql\n{sql}\n```\n\n"
                        f"Error: {last_error}\n\n"
                        f"Rewrite the SQL to fix this error. "
                        f"Return ONLY the corrected SQL, no explanation."
                    )
                    try:
                        fix_response = llm.invoke(fix_prompt)
                        fixed = fix_response.content if hasattr(fix_response, "content") else str(fix_response)
                        fixed = re.sub(r"^```(?:sql)?\s*", "", fixed, flags=re.I)
                        fixed = re.sub(r"\s*```$", "", fixed).strip()
                        if fixed:
                            sql = fixed
                            continue
                    except Exception:
                        pass
                break

        return f"SQL execution failed after 3 attempts.\nLast error: {last_error}\nLast SQL tried:\n{sql}"

    # ------------------------------------------------------------------
    # Tool 4 — Search past queries (episodic memory via pgvector)
    # ------------------------------------------------------------------
    @tool
    def search_past_queries(query: str) -> str:
        """
        Search conversation history for similar past questions and the SQL that answered them.
        
        Useful for: finding reusable SQL patterns, understanding what has been asked before,
        avoiding rewriting SQL from scratch for common questions.
        
        Args:
            query: Natural language description of what you're looking for
        """
        if chat_history is None:
            return "Chat history not available."
        try:
            similar = chat_history.search_similar_messages(query, limit=5)
            if not similar:
                return "No similar past queries found."
            results = []
            for msg in similar:
                content = msg.get("content", "")
                role = msg.get("role", "")
                score = msg.get("similarity_score", 0)
                # Only include messages that contain SQL
                if "SELECT" in content.upper() or role == "user":
                    results.append(
                        f"[similarity={score:.2f}] [{role}]: {content[:500]}"
                    )
            return "\n\n".join(results) if results else "No relevant past queries found."
        except Exception as e:
            return f"Error searching past queries: {e}"

    # ------------------------------------------------------------------
    # Tool 5 — Run a named business calculation
    # ------------------------------------------------------------------
    @tool
    def calculate_metric(metric_name: str, params_json: str = "{}") -> str:
        """
        Run a pre-defined business calculation (e.g. churn_rate, ltv, conversion_rate).
        
        Use this for complex KPIs that combine multiple SQL queries or apply
        specific business formula logic defined in the config.
        
        Args:
            metric_name: Name of the calculation (e.g. "churn_rate", "monthly_revenue_growth")
            params_json: JSON string of parameters e.g. '{"period": "2024-Q1"}'
        """
        if config_manager is None:
            return "Config manager not available — cannot run business calculations."
        try:
            params = json.loads(params_json) if params_json else {}
        except json.JSONDecodeError:
            return f"Invalid params_json — must be a valid JSON object string. Got: {params_json}"

        try:
            calculations = config_manager.get_all_calculations()
            calc = next((c for c in calculations if c.name.lower() == metric_name.lower()), None)
            if calc is None:
                available = [c.name for c in calculations]
                return (
                    f"Calculation '{metric_name}' not found. "
                    f"Available: {', '.join(available) or 'none'}"
                )

            # Build the SQL from the calculation's formula + parameters
            formula_sql = calc.formula
            for key, val in params.items():
                formula_sql = formula_sql.replace(f"{{{key}}}", str(val))

            df = bq_connector.execute_query(formula_sql)
            result = {
                "metric": metric_name,
                "params": params,
                "columns": df.columns.tolist() if df is not None else [],
                "rows": df.head(100).to_dict(orient="records") if df is not None else [],
            }
            return json.dumps(result, default=str)
        except Exception as e:
            return f"Error running calculation '{metric_name}': {e}"

    # ------------------------------------------------------------------
    # Tool 6 — Validate SQL before executing
    # ------------------------------------------------------------------
    @tool
    def validate_sql(sql: str) -> str:
        """
        Validate a SQL query using BigQuery's dry-run (no charge, no execution).
        
        Use this before execute_sql when you're unsure about column names or
        table structure to avoid wasted attempts.
        
        Args:
            sql: GoogleSQL SELECT statement to validate
        """
        sql = sql.strip()
        sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.I)
        sql = re.sub(r"\s*```$", "", sql).strip()

        try:
            result = bq_connector.validate_query(sql)
            if result.get("valid"):
                bytes_est = result.get("bytes_processed", 0)
                mb = (bytes_est or 0) / (1024 * 1024)
                return f"SQL is valid. Estimated data scanned: {mb:.1f} MB."
            else:
                return f"SQL validation failed: {result.get('error', 'unknown error')}"
        except Exception as e:
            return f"Could not validate SQL: {e}"

    return [
        search_schema,
        list_tables,
        execute_sql,
        search_past_queries,
        calculate_metric,
        validate_sql,
    ]
