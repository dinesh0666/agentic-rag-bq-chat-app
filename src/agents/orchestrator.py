"""
Agentic RAG Orchestrator — LangGraph ReAct agent with tool-calling and schema RAG.

Architecture:
  1. SchemaVectorStore indexes BigQuery schemas at startup (real RAG retrieval)
  2. LangGraph ReAct agent decides which tools to call and in what order
  3. Tools: search_schema, list_tables, validate_sql, execute_sql,
             search_past_queries, calculate_metric
  4. SQL self-correction loop lives inside the execute_sql tool (up to 3 retries)
  5. After the agent retrieves data, a streaming LLM call narrates the result
"""

import json
import os
from typing import Any, Dict, Generator, Optional

import pandas as pd
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.prebuilt import create_react_agent

from ..config import ConfigManager
from ..connectors import BigQueryConnector
from ..knowledge import SchemaVectorStore
from ..llm import LLMFactory
from ..visualization import DataVisualizer
from .tools import build_tools


# ---------------------------------------------------------------------------
# Tool -> friendly status message mapping
# ---------------------------------------------------------------------------
_TOOL_STATUS = {
    "search_schema":       "Retrieving relevant schema...",
    "list_tables":         "Listing available tables...",
    "validate_sql":        "Validating SQL...",
    "execute_sql":         "Running query on BigQuery...",
    "search_past_queries": "Searching conversation memory...",
    "calculate_metric":    "Running business calculation...",
}


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class AgenticRAG:
    """
    Genuinely agentic RAG system.

    The LLM autonomously decides which tools to call (and in what order)
    to answer each question — no hard-coded SQL pipeline.
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        bq_connector: BigQueryConnector,
        llm_provider: Optional[str] = None,
        chat_history=None,
    ):
        self.config_manager = config_manager
        self.bq_connector = bq_connector
        self.primary_provider = llm_provider or os.getenv("LLM_PROVIDER", "ollama")
        self.fallback_provider = os.getenv("LLM_FALLBACK_PROVIDER", "gemini")
        self.using_fallback = False
        self.fallback_llm = None
        self.visualizer = DataVisualizer()
        self.chat_history = chat_history

        # Primary LLM
        self.llm = LLMFactory.get_llm(
            provider_name=self.primary_provider, temperature=0.1
        )

        # Schema RAG - index at startup
        self.schema_store = SchemaVectorStore()
        self._warm_up_schema_store()

        # ReAct agent
        self._rebuild_agent()

    # ------------------------------------------------------------------
    # LLM helpers
    # ------------------------------------------------------------------

    def _get_llm(self):
        if self.using_fallback:
            if self.fallback_llm is None:
                try:
                    print(f"[INFO] Initializing fallback LLM: {self.fallback_provider}")
                    self.fallback_llm = LLMFactory.get_llm(
                        provider_name=self.fallback_provider, temperature=0.1
                    )
                    print(f"[INFO] Fallback LLM ({self.fallback_provider}) ready")
                except Exception as e:
                    print(f"[ERROR] Fallback LLM init failed: {e}")
                    self.using_fallback = False
                    return self.llm
            return self.fallback_llm
        return self.llm

    def _handle_llm_error(self, error: Exception) -> bool:
        """Switch to fallback on quota/rate-limit errors. Returns True if should retry."""
        msg = str(error).lower()
        if any(k in msg for k in ["resource_exhausted", "quota", "rate limit", "429", "503"]):
            if not self.using_fallback:
                print(f"[WARNING] Primary LLM failed: {error}")
                print(f"[INFO] Switching to fallback: {self.fallback_provider}")
                self.using_fallback = True
                return True
        return False

    # ------------------------------------------------------------------
    # Schema RAG warm-up
    # ------------------------------------------------------------------

    def _warm_up_schema_store(self):
        print("[RAG] Warming up schema vector store...")
        try:
            schemas = self.bq_connector.get_all_schemas()
            self.schema_store.index_schemas(schemas)

            calcs = []
            try:
                calcs = self.config_manager.get_all_calculations() or []
            except Exception:
                pass

            domain = ""
            try:
                domain = self.config_manager.get_domain_context() or ""
            except Exception:
                pass

            if calcs or domain:
                self.schema_store.index_business_rules(calcs, domain_info=domain)

            print(f"[RAG] Schema store ready with {len(self.schema_store.documents)} chunks indexed")
        except Exception as e:
            print(f"[WARNING] Schema store warm-up failed: {e}")

    # ------------------------------------------------------------------
    # Agent builder
    # ------------------------------------------------------------------

    def _rebuild_agent(self):
        """(Re)build the LangGraph ReAct agent with current LLM."""
        llm = self._get_llm()
        tools = build_tools(
            bq_connector=self.bq_connector,
            schema_store=self.schema_store,
            chat_history=self.chat_history,
            config_manager=self.config_manager,
            llm=llm,
        )
        self._tools = tools
        self.agent = create_react_agent(llm, tools)
        print(f"[AGENT] ReAct agent built with {len(tools)} tools")

    # ------------------------------------------------------------------
    # System prompt (RAG-augmented)
    # ------------------------------------------------------------------

    def _build_system_prompt(self, query: str) -> str:
        rag_context = self.schema_store.get_relevant_schema_context(query, k=12)
        billing = self.bq_connector.project_id
        data_proj = self.bq_connector.data_project_id
        dataset = self.bq_connector.dataset_id

        try:
            domain_ctx = self.config_manager.get_domain_context() or ""
        except Exception:
            domain_ctx = ""

        return f"""You are an expert data analyst with access to a BigQuery dataset.
Your job is to answer the user's question by intelligently using the available tools.

{domain_ctx}

BigQuery Configuration:
- Billing project: {billing}
- Data location: `{data_proj}.{dataset}`
- Always use fully qualified table names: `{data_proj}.{dataset}.table_name`

{rag_context}

Guidelines:
1. ALWAYS call search_schema first to retrieve relevant schema details before writing SQL
2. Write precise GoogleSQL (BigQuery dialect) with backtick-quoted fully qualified table names
3. If execute_sql fails, the tool auto-corrects up to 3 times - let it handle retries
4. If unsure about column names, call validate_sql before execute_sql
5. For business KPIs (churn, LTV, etc.), prefer calculate_metric over raw SQL
6. Keep your final answer concise: 2-4 sentences, lead with key numbers
7. Do NOT dump raw data in your response - the UI renders charts automatically
"""

    # ------------------------------------------------------------------
    # Primary streaming interface (used by app.py)
    # ------------------------------------------------------------------

    def stream_response(self, query: str) -> Generator[Dict[str, Any], None, None]:
        """
        Stream the agentic RAG response.

        Yields dicts with 'type' key:
          {"type": "status",   "content": str}
          {"type": "metadata", "sql_query": str, "data": DataFrame,
                               "visualization": Figure, "error": str,
                               "calculation_result": Any, "intent_route": str}
          {"type": "text",     "content": str}
          {"type": "error",    "content": str}
        """
        captured_sql: Optional[str] = None
        captured_df: Optional[pd.DataFrame] = None
        captured_calc: Optional[Any] = None
        agent_error: Optional[str] = None
        final_answer: Optional[str] = None

        try:
            yield {"type": "status", "content": "Thinking and retrieving schema..."}

            system_msg = SystemMessage(content=self._build_system_prompt(query))
            human_msg = HumanMessage(content=query)
            input_messages = {"messages": [system_msg, human_msg]}

            # ----------------------------------------------------------------
            # Phase 1 - Run the ReAct agent loop, capture SQL & data
            # ----------------------------------------------------------------
            for event in self.agent.stream(input_messages, stream_mode="values"):
                messages = event.get("messages", [])
                if not messages:
                    continue

                last_msg = messages[-1]

                # Agent is calling a tool
                if isinstance(last_msg, AIMessage) and getattr(last_msg, "tool_calls", None):
                    for tc in last_msg.tool_calls:
                        tool_name = tc.get("name", "")
                        status = _TOOL_STATUS.get(tool_name, f"Running {tool_name}...")
                        yield {"type": "status", "content": status}

                # Tool returned a result
                elif isinstance(last_msg, ToolMessage):
                    tool_name = getattr(last_msg, "name", "")
                    content = last_msg.content or ""

                    if tool_name == "execute_sql":
                        try:
                            result = json.loads(content)
                            rows = result.get("rows", [])
                            cols = result.get("columns", [])
                            sql = result.get("sql_executed", "")
                            if rows and cols:
                                captured_df = pd.DataFrame(rows, columns=cols)
                                captured_sql = sql
                            elif "failed" in content.lower():
                                agent_error = content
                        except Exception:
                            if "failed" in content.lower():
                                agent_error = content

                    elif tool_name == "calculate_metric":
                        try:
                            result = json.loads(content)
                            rows = result.get("rows", [])
                            cols = result.get("columns", [])
                            if rows and cols:
                                captured_df = pd.DataFrame(rows, columns=cols)
                                captured_calc = result.get("metric")
                        except Exception:
                            pass

                # Agent final textual answer (no more tool calls)
                elif isinstance(last_msg, AIMessage) and last_msg.content:
                    if not getattr(last_msg, "tool_calls", None):
                        final_answer = last_msg.content

            # ----------------------------------------------------------------
            # Phase 2 - Create visualization
            # ----------------------------------------------------------------
            visualization = None
            if captured_df is not None and not captured_df.empty:
                yield {"type": "status", "content": "Building chart..."}
                try:
                    chart_type = None
                    q_lower = query.lower()
                    chart_map = {
                        "pie":       ["pie", "donut"],
                        "bar":       ["bar chart", "bar graph", "bar"],
                        "line":      ["line chart", "line graph", "trend", "over time", "time series"],
                        "scatter":   ["scatter", "scatterplot"],
                        "histogram": ["histogram", "distribution"],
                    }
                    for ctype, keywords in chart_map.items():
                        if any(kw in q_lower for kw in keywords):
                            chart_type = ctype
                            break
                    visualization = self.visualizer.auto_visualize(
                        captured_df, chart_type=chart_type
                    )
                    if visualization:
                        title = query.strip().rstrip("?").capitalize()
                        visualization.update_layout(title=title[:60])
                except Exception as ve:
                    print(f"[WARNING] Visualization failed: {ve}")

            # ----------------------------------------------------------------
            # Phase 3 - Yield metadata to front-end
            # ----------------------------------------------------------------
            yield {
                "type": "metadata",
                "sql_query": captured_sql,
                "data": captured_df,
                "visualization": visualization,
                "calculation_result": captured_calc,
                "error": agent_error,
                "intent_route": "sql" if captured_sql else (
                    "calculation" if captured_calc else "general"
                ),
            }

            if agent_error and not final_answer:
                yield {
                    "type": "text",
                    "content": f"I ran into an issue: {agent_error}\n\nPlease try rephrasing.",
                }
                return

            # ----------------------------------------------------------------
            # Phase 4 - Stream the final narrative response
            # ----------------------------------------------------------------
            yield {"type": "status", "content": "Composing answer..."}

            wants_deep = query.lower().startswith("generate detailed insights")

            if final_answer and not wants_deep:
                # Emit agent answer word by word
                words = final_answer.split(" ")
                for i, word in enumerate(words):
                    yield {
                        "type": "text",
                        "content": word + ("" if i == len(words) - 1 else " "),
                    }
            else:
                # Build focused LLM narration prompt
                context_parts = []
                if captured_df is not None and not captured_df.empty:
                    context_parts.append(f"Rows returned: {len(captured_df)}")
                    context_parts.append(captured_df.head(10).to_string(index=False))
                    if len(captured_df) > 10:
                        context_parts.append(f"... ({len(captured_df)} total rows)")
                if captured_calc:
                    context_parts.append(f"Metric: {captured_calc}")
                if final_answer:
                    context_parts.append(f"\nAgent finding: {final_answer}")

                ctx = "\n".join(context_parts) or "No data returned."

                if wants_deep:
                    orig_q = query.split(":", 1)[-1].strip() if ":" in query else query
                    prompt = f"""You are a senior data analyst. Provide deep, actionable insights.

Original Question: {orig_q}

Data:
{ctx}

Generate a comprehensive analysis with:
1. **Key Findings** - 2-3 main takeaways with specific numbers
2. **Trends & Patterns** - notable patterns or anomalies
3. **Business Context** - what this means for stakeholders
4. **Actionable Recommendations** - concrete next steps

Use bullet points and bold key numbers."""
                else:
                    prompt = f"""You are a concise data analyst. Answer the user's question directly.

Question: {query}

Data:
{ctx}

Rules:
- Answer in 2-4 sentences maximum
- Lead with the key number / finding
- Use commas for large numbers (e.g. $1,234,567)
- Do NOT list every row or repeat the table
- If a visualization was created, mention it briefly at the end
"""
                retry_count = 0
                while retry_count < 2:
                    try:
                        llm = self._get_llm()
                        for chunk in llm.stream([HumanMessage(content=prompt)]):
                            if hasattr(chunk, "content") and chunk.content:
                                yield {"type": "text", "content": chunk.content}
                        break
                    except Exception as llm_err:
                        if self._handle_llm_error(llm_err):
                            retry_count += 1
                            self._rebuild_agent()
                            continue
                        raise llm_err

        except Exception as e:
            import traceback
            traceback.print_exc()
            err = str(e)
            if any(k in err.lower() for k in ["resource_exhausted", "quota", "429"]):
                yield {
                    "type": "error",
                    "content": (
                        "API quota exceeded. Ensure Ollama is running locally "
                        "(http://localhost:11434) or wait for limits to reset.\n\n"
                        f"Error: {err}"
                    ),
                }
            else:
                yield {"type": "error", "content": f"An error occurred: {err}"}

    # ------------------------------------------------------------------
    # Non-streaming fallback (used by cli.py / tests)
    # ------------------------------------------------------------------

    def process_query(self, query: str) -> Dict[str, Any]:
        """Run a complete query and return the result dict (non-streaming)."""
        result = {
            "response": "",
            "data": None,
            "visualization": None,
            "sql_query": None,
            "calculation_result": None,
            "error": None,
        }
        text_parts = []

        for chunk in self.stream_response(query):
            ctype = chunk.get("type")
            if ctype == "text":
                text_parts.append(chunk.get("content", ""))
            elif ctype == "metadata":
                result["data"] = chunk.get("data")
                result["sql_query"] = chunk.get("sql_query")
                result["visualization"] = chunk.get("visualization")
                result["calculation_result"] = chunk.get("calculation_result")
                result["error"] = chunk.get("error")
            elif ctype == "error":
                result["error"] = chunk.get("content")

        result["response"] = "".join(text_parts)
        return result

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def get_dataset_overview(self) -> str:
        """Return a formatted markdown overview of indexed tables."""
        try:
            schemas = self.bq_connector.get_all_schemas()
            lines = ["**Dataset Overview**\n"]
            for schema in schemas:
                cols = schema.get("columns", [])
                col_str = ", ".join(
                    f"{c['name']} ({c['type']})" for c in cols[:10]
                )
                if len(cols) > 10:
                    col_str += f" and {len(cols) - 10} more"
                lines.append(f"**{schema['table_name']}**: {col_str}\n")
            return "\n".join(lines)
        except Exception as e:
            return f"Error getting dataset overview: {e}"
