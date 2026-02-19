"""Streamlit chat interface for the Agentic RAG application."""

import os
import uuid
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv
import pandas as pd

from src.agents import AgenticRAG
from src.config import ConfigManager
from src.connectors import BigQueryConnector
from src.llm import LLMFactory
from src.storage import ChatHistoryStore

# Load environment variables
load_dotenv()


def generate_contextual_prompts(user_query: str, result: dict) -> list:
    """Generate intelligent contextual follow-up prompts based on user query and results."""
    query_lower = user_query.lower()
    prompts = []
    
    # Extract key entities from the query
    has_data = result.get("data") is not None and not result.get("data").empty
    
    # Brand/Product related
    if any(word in query_lower for word in ["brand", "product", "vendor", "item", "description"]):
        prompts.extend([
            "Visualize these brands as a bar chart with sales comparison",
            "Show monthly sales trends for these brands over time",
            "Break down by county - which regions buy these brands most?",
            "Compare profit margins between these brands"
        ])
    
    # Geographic related
    elif any(word in query_lower for word in ["county", "city", "location", "region", "store", "zip"]):
        prompts.extend([
            "Create a map visualization showing sales by geography",
            "What are the top liquor categories in these regions?",
            "Show me year-over-year growth trends for these locations",
            "Visualize the distribution as a pie chart"
        ])
    
    # Category/Type related
    elif any(word in query_lower for word in ["category", "type", "vodka", "whiskey", "rum", "tequila", "gin", "liqueur"]):
        prompts.extend([
            "Visualize category sales as a pie chart",
            "Show time series trend - how has this category grown?",
            "Which brands dominate this category? Show top 10",
            "Compare bottle sizes and volumes for this category"
        ])
    
    # Time/Trend related
    elif any(word in query_lower for word in ["trend", "month", "year", "time", "growth", "over time", "by month"]):
        prompts.extend([
            "Show this as a line chart to see the trend clearly",
            "Identify seasonal patterns - compare each quarter",
            "Compare with previous year - calculate YoY growth",
            "Which products had the biggest growth? Visualize top movers"
        ])
    
    # Top/Ranking queries
    elif any(word in query_lower for word in ["top", "highest", "most", "best", "largest", "biggest"]):
        prompts.extend([
            "Visualize this ranking as a horizontal bar chart",
            "Show the percentage breakdown as a pie chart",
            "How do these compare by county? Create a comparison chart",
            "What's the trend over time for these top performers?"
        ])
    
    # Sales/Revenue related
    elif any(word in query_lower for word in ["sales", "revenue", "dollars", "profit", "margin"]):
        prompts.extend([
            "Show sales distribution by category as a pie chart",
            "Visualize monthly revenue trends as a line graph",
            "Calculate and compare profit margins across products",
            "Which regions contribute most? Create a bar chart"
        ])
    
    # Comparison queries
    elif any(word in query_lower for word in ["compare", "vs", "versus", "difference", "between"]):
        prompts.extend([
            "Create a side-by-side comparison chart",
            "Show the difference as a grouped bar chart",
            "Visualize percentage differences as a waterfall chart",
            "Break down by time period - show trends for each"
        ])
    
    # Default intelligent suggestions based on available data
    else:
        if has_data:
            prompts.extend([
                "Visualize this data as an interactive chart",
                "Show me the trends over time for these results",
                "Break this down by category and create a chart",
                "Compare these results across different regions"
            ])
        else:
            prompts.extend([
                "Show top 10 brands by sales with bar chart",
                "Visualize monthly sales trends as line graph",
                "Compare sales across Iowa counties on a map",
                "What are the best-selling categories? Show as pie chart"
            ])
    
    return prompts[:4]  # Return top 4 suggestions

# Page configuration
st.set_page_config(
    page_title="Agentic RAG - BigQuery Chat",
    page_icon="🤖",
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stAlert {
        margin-top: 1rem;
    }
    </style>
""", unsafe_allow_html=True)


@st.cache_resource
def initialize_system():
    """Initialize the system components."""
    try:
        config_manager = ConfigManager()
        bq_connector = BigQueryConnector()
        agent = AgenticRAG(
            config_manager=config_manager,
            bq_connector=bq_connector
        )
        
        # Initialize chat history store (will work without PostgreSQL)
        try:
            chat_history = ChatHistoryStore()
        except Exception as e:
            print(f"[WARNING] Chat history store initialization failed: {e}")
            chat_history = None
        
        return agent, config_manager, bq_connector, chat_history
    except Exception as e:
        error_msg = str(e)
        if "authentication" in error_msg.lower() or "credentials" in error_msg.lower():
            st.error("🔐 BigQuery Authentication Required")
            st.markdown("""
            To use this app with BigQuery (including public datasets), you need to authenticate.
            
            **Quick Setup (Recommended):**
            
            1. **Install Google Cloud SDK:**
               - Mac: `brew install google-cloud-sdk`
               - Or download from: https://cloud.google.com/sdk/docs/install
            
            2. **Authenticate:**
               ```bash
               gcloud auth application-default login
               ```
               This will open your browser to sign in with your Google account.
            
            3. **Restart the app:**
               ```bash
               make run
               ```
            
            **Alternative: Use Service Account**
            - Download a service account JSON key from Google Cloud Console
            - Set `GOOGLE_APPLICATION_CREDENTIALS` in your `.env` file to the path of the JSON file
            
            ---
            
            **Note:** Even public datasets like Iowa Liquor Sales require authentication.
            Authentication is free and only takes a minute to set up!
            """)
        else:
            import traceback
            traceback.print_exc()
            st.error(f"Initialization error: {str(e)}")
        return None, None, None, None


def main():
    """Main Streamlit application."""
    
    st.title("🤖 Agentic RAG - BigQuery Chat")
    st.markdown("Chat with your data using natural language powered by AI agents")
    
    # Initialize system
    agent, config_manager, bq_connector, chat_history = initialize_system()
    
    if agent is None:
        # Error messages are shown in initialize_system()
        return
    
    # Initialize session ID for chat history
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
        if chat_history:
            chat_history.create_session(
                st.session_state.session_id,
                metadata={"started_at": datetime.now().isoformat()}
            )
    
    # Initialize cancel flag
    if "cancel_generation" not in st.session_state:
        st.session_state.cancel_generation = False
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Display client info
        if config_manager.config:
            st.success(f"Client: {config_manager.config.client_name}")
            
            # Display available tables
            with st.expander("📊 Available Tables"):
                try:
                    tables = bq_connector.get_tables()
                    for table in tables:
                        st.write(f"- {table}")
                except Exception as e:
                    st.error(f"Error loading tables: {str(e)}")
            
            # Display business calculations
            with st.expander("🧮 Business Calculations"):
                calcs = config_manager.get_all_calculations()
                if calcs:
                    for calc in calcs:
                        st.write(f"**{calc.name}**")
                        st.write(f"_{calc.description}_")
                        if calc.formula:
                            st.code(calc.formula, language="python")
                        st.divider()
                else:
                    st.info("No calculations configured")
        else:
            st.warning("No configuration loaded")
        
        st.divider()
        
        # Settings
        st.subheader("Settings")
        show_sql = st.checkbox("Show SQL Queries", value=False)
        show_data = st.checkbox("Show Raw Data", value=True)
        
        # Chat History Management
        if chat_history:
            st.divider()
            st.subheader("💾 Chat History")
            
            sessions = chat_history.get_all_sessions()
            if sessions:
                st.info(f"📚 {len(sessions)} saved sessions")
                
                with st.expander("View Past Sessions"):
                    for session in sessions[:10]:  # Show recent 10
                        # Get first user message as preview
                        preview = "No messages"
                        try:
                            messages = chat_history.get_session_history(session['session_id'], limit=1)
                            if messages:
                                preview = messages[0]['content'][:60] + "..." if len(messages[0]['content']) > 60 else messages[0]['content']
                        except:
                            pass
                        
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.text(f"🕐 {session['updated_at'].strftime('%Y-%m-%d %H:%M')}")
                            st.caption(f"💬 {session['message_count']} messages | {preview}")
                        with col2:
                            if st.button("Load", key=f"load_{session['session_id'][:8]}"):
                                # Load session history from database
                                st.session_state.session_id = session['session_id']
                                
                                # Load messages from database
                                loaded_messages = chat_history.get_session_history(session['session_id'])
                                st.session_state.messages = []
                                
                                # Convert database messages to Streamlit format
                                for msg in loaded_messages:
                                    message_dict = {
                                        "role": msg["role"],
                                        "content": msg["content"]
                                    }
                                    
                                    # Add metadata if available
                                    if msg.get("metadata"):
                                        metadata = msg["metadata"]
                                        if isinstance(metadata, str):
                                            import json
                                            metadata = json.loads(metadata)
                                        
                                        if metadata.get("sql_query"):
                                            message_dict["sql"] = metadata["sql_query"]
                                    
                                    st.session_state.messages.append(message_dict)
                                
                                st.success(f"✅ Loaded {len(loaded_messages)} messages")
                                st.rerun()
            else:
                st.caption("No saved sessions yet")
                
            # Search similar conversations
            st.divider()
            st.subheader("🔍 Search History")
            search_query = st.text_input("Search past conversations", placeholder="e.g., sales trends")
            if search_query:
                similar = chat_history.search_similar_messages(search_query, limit=3)
                if similar:
                    for msg in similar:
                        with st.expander(f"✨ {msg['role'].title()} ({msg['similarity']:.2%} match)"):
                            st.write(msg['content'])
                            st.caption(f"Session: {msg['session_id'][:8]} • {msg['created_at'].strftime('%Y-%m-%d %H:%M')}")
                else:
                    st.info("No similar conversations found")
        else:
            st.divider()
            st.caption("💡 Enable PostgreSQL to save chat history")
        
        if st.button("🗑️ Clear Current Chat"):
            if chat_history and "session_id" in st.session_state:
                # Start new session
                st.session_state.session_id = str(uuid.uuid4())
                chat_history.create_session(
                    st.session_state.session_id,
                    metadata={"started_at": datetime.now().isoformat()}
                )
            st.session_state.messages = []
            st.rerun()
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
        
        # If session_id exists and chat_history available, try to load messages
        if chat_history and "session_id" in st.session_state:
            try:
                loaded_messages = chat_history.get_session_history(st.session_state.session_id)
                if loaded_messages:
                    # Convert database messages to Streamlit format
                    for msg in loaded_messages:
                        message_dict = {
                            "role": msg["role"],
                            "content": msg["content"]
                        }
                        
                        # Add metadata if available
                        if msg.get("metadata"):
                            import json
                            metadata = msg["metadata"]
                            if isinstance(metadata, str):
                                metadata = json.loads(metadata)
                            
                            if metadata.get("sql_query"):
                                message_dict["sql"] = metadata["sql_query"]
                        
                        st.session_state.messages.append(message_dict)
            except Exception as e:
                print(f"[INFO] Could not load session history: {e}")
    
    # Initialize suggested prompts
    if "suggested_prompts" not in st.session_state:
        st.session_state.suggested_prompts = [
            "Show me top 10 liquor brands by sales revenue",
            "What are the sales trends by month in 2023?",
            "Compare sales across Iowa counties",
            "Which stores have the highest profit margins?"
        ]
    
    # Quick prompt buttons (shown when chat is empty or after responses)
    if len(st.session_state.messages) == 0:
        st.markdown("### 📊 Analytics & Insights - Try asking:")
        cols = st.columns(2)
        quick_prompts = [
            "📈 Top 10 liquor brands by sales revenue",
            "📅 Monthly sales trends in 2023",
            "🗺️ Compare sales by county",
            "🏆 Most popular liquor categories"
        ]
        for idx, prompt in enumerate(quick_prompts):
            with cols[idx % 2]:
                if st.button(prompt, key=f"quick_{idx}", use_container_width=True):
                    # Remove emoji for actual query
                    clean_prompt = prompt.split(" ", 1)[1] if " " in prompt else prompt
                    st.session_state.prompt_clicked = clean_prompt
                    st.rerun()
    
    # Display chat history
    for idx, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            # Show visualization FIRST (most important)
            if "visualization" in message and message["visualization"] is not None:
                st.plotly_chart(message["visualization"], use_container_width=True, key=f"hist_viz_{idx}")
            
            # Then insights/content
            st.markdown(message["content"])
            
            # Show metadata (timestamp, tokens, cost) for both user and assistant messages
            if message.get("metadata"):
                meta = message["metadata"]
                meta_parts = []
                
                if meta.get("timestamp"):
                    try:
                        ts = datetime.fromisoformat(meta["timestamp"])
                        meta_parts.append(f"🕒 {ts.strftime('%I:%M:%S %p')}")
                    except:
                        pass
                
                # For assistant messages, show tokens and cost
                if message["role"] == "assistant":
                    if meta.get("tokens"):
                        meta_parts.append(f"🔢 ~{meta['tokens']:,} tokens")
                    if meta.get("cost"):
                        meta_parts.append(f"💰 ~${meta['cost']:.4f}")
                    if meta.get("duration"):
                        meta_parts.append(f"⏱️ {meta['duration']:.1f}s")
                
                if meta_parts:
                    st.caption(" • ".join(meta_parts))
            
            # Data table (collapsed to prioritize insights)
            if "data" in message and message["data"] is not None:
                if not message["data"].empty and show_data:
                    with st.expander(f"📊 View Raw Data ({len(message['data'])} rows)"):
                        st.dataframe(message["data"], use_container_width=True, height=300)
            
            # SQL query (for technical users)
            if "sql" in message and message["sql"] and show_sql:
                with st.expander("📝 View SQL Query"):
                    st.code(message["sql"], language="sql")
            
            # Show contextual suggestions after assistant responses
            if message["role"] == "assistant" and idx == len(st.session_state.messages) - 1:
                if len(st.session_state.suggested_prompts) > 0:
                    st.markdown("---")
                    suggestions = st.session_state.suggested_prompts
                    # Check if first suggestion is "Generate Insights"
                    if suggestions and suggestions[0].startswith("Generate detailed insights"):
                        st.markdown("##### 🔍 Want more depth?")
                        if st.button(f"📊 Generate Deep Insights", key=f"insights_{idx}", use_container_width=True, type="primary"):
                            st.session_state.prompt_clicked = suggestions[0]
                            st.rerun()
                        if len(suggestions) > 1:
                            st.markdown("##### 🔮 Follow-up analysis:")
                            suggestion_cols = st.columns(2)
                            for s_idx, suggestion in enumerate(suggestions[1:4]):
                                with suggestion_cols[s_idx % 2]:
                                    if st.button(f"💡 {suggestion}", key=f"suggest_{idx}_{s_idx}", use_container_width=True):
                                        st.session_state.prompt_clicked = suggestion
                                        st.rerun()
                    else:
                        st.markdown("##### 🔮 Follow-up analysis:")
                        suggestion_cols = st.columns(2)
                        for s_idx, suggestion in enumerate(suggestions[:4]):
                            with suggestion_cols[s_idx % 2]:
                                if st.button(f"💡 {suggestion}", key=f"suggest_{idx}_{s_idx}", use_container_width=True):
                                    st.session_state.prompt_clicked = suggestion
                                    st.rerun()
    
    # Chat input - placed at the bottom for visibility (sticky by default in Streamlit)
    prompt = st.chat_input("💬 Ask me to analyze your data, create visualizations, or explore insights...")
    
    # Check if a prompt button was clicked
    if "prompt_clicked" in st.session_state:
        prompt = st.session_state.prompt_clicked
        del st.session_state.prompt_clicked
    
    if prompt:
        # Add user message to chat history with timestamp
        user_timestamp = datetime.now()
        st.session_state.messages.append({
            "role": "user", 
            "content": prompt,
            "metadata": {"timestamp": user_timestamp.isoformat()}
        })
        
        # Save user message to PostgreSQL
        if chat_history:
            chat_history.add_message(
                session_id=st.session_state.session_id,
                role="user",
                content=prompt,
                metadata={"timestamp": user_timestamp.isoformat()}
            )
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
            st.caption(f"🕒 {user_timestamp.strftime('%I:%M:%S %p')}")
        
        # Process query with agent using streaming
        with st.chat_message("assistant"):
            try:
                # Containers for different parts of the response
                cols = st.columns([6, 1])
                with cols[1]:
                    cancel_button = st.button("🛑 Cancel", key="cancel_btn")
                    if cancel_button:
                        st.session_state.cancel_generation = True
                
                status_container = st.empty()
                viz_container = st.container()
                response_placeholder = st.empty()
                data_container = st.container()
                sql_container = st.container()
                calc_container = st.container()
                metadata_container = st.empty()
                
                status_container.markdown("⏳ *Starting...*")
                
                # Reset cancel flag
                st.session_state.cancel_generation = False
                
                # Collect streaming response
                metadata_result = None
                response_chunks = []
                start_time = datetime.now()
                total_tokens = 0
                
                for chunk in agent.stream_response(prompt):
                    # Check for cancellation
                    if st.session_state.cancel_generation:
                        status_container.warning("⚠️ Generation cancelled by user")
                        break
                    
                    if chunk["type"] == "status":
                        # Show live step progress
                        status_container.markdown(f"*{chunk['content']}*")

                    elif chunk["type"] == "metadata":
                        # Store metadata (SQL, data, visualization)
                        metadata_result = chunk
                        status_container.markdown("✍️ *Writing answer...*")
                        
                        # Display visualization first if available
                        if chunk.get("visualization") is not None:
                            with viz_container:
                                st.plotly_chart(chunk["visualization"], use_container_width=True, key=f"viz_{len(st.session_state.messages)}")
                        
                        # Display error if present
                        if chunk.get("error"):
                            status_container.empty()
                            response_placeholder.error(f"⚠️ {chunk['error']}")
                            if chunk.get("sql_query"):
                                with sql_container:
                                    with st.expander("🔍 View Generated SQL"):
                                        st.code(chunk["sql_query"], language="sql")
                    
                    elif chunk["type"] == "text":
                        # Stream text response in real-time
                        response_chunks.append(chunk["content"])
                        current_text = "".join(response_chunks)
                        response_placeholder.markdown(current_text + "▌")  # Show cursor
                        
                        # Estimate tokens (rough: ~4 chars per token)
                        total_tokens = len(current_text) // 4
                    
                    elif chunk["type"] == "error":
                        status_container.empty()
                        response_placeholder.error(chunk["content"])
                        break
                
                # Clear status and finalize response
                status_container.empty()
                
                # Remove cursor from final response
                if response_chunks:
                    final_text = "".join(response_chunks)
                    response_placeholder.markdown(final_text)
                
                # Calculate final metrics
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                # Estimate cost (rough: ~$0.0004 per 1K tokens, varies by provider)
                estimated_cost = (total_tokens / 1000) * 0.0004
                
                # Combine response
                full_response = "".join(response_chunks) if response_chunks else "No response generated"
                
                # Show completion metadata
                if total_tokens > 0 and not st.session_state.cancel_generation:
                    metadata_container.caption(f"🕒 {end_time.strftime('%I:%M:%S %p')} • 🔢 ~{total_tokens:,} tokens • 💰 ~${estimated_cost:.4f} • ⏱️ {duration:.1f}s")
                
                # Store message with all data
                message_data = {
                    "role": "assistant",
                    "content": full_response,
                    "metadata": {
                        "timestamp": end_time.isoformat(),
                        "tokens": total_tokens,
                        "cost": estimated_cost,
                        "duration": duration
                    }
                }
                
                if metadata_result:
                    # Display data table (collapsed by default to focus on insights)
                    if metadata_result.get("data") is not None and not metadata_result["data"].empty:
                        message_data["data"] = metadata_result["data"]
                        if show_data:
                            with data_container:
                                with st.expander(f"📊 View Raw Data ({len(metadata_result['data'])} rows)"):
                                    st.dataframe(metadata_result["data"], use_container_width=True, height=300)
                    
                    # Store visualization
                    if metadata_result.get("visualization") is not None:
                        message_data["visualization"] = metadata_result["visualization"]
                    
                    # Store and display SQL query
                    if metadata_result.get("sql_query"):
                        message_data["sql"] = metadata_result["sql_query"]
                        if show_sql:
                            with sql_container:
                                with st.expander("📝 View SQL Query"):
                                    st.code(metadata_result["sql_query"], language="sql")
                    
                    # Display calculation result
                    if metadata_result.get("calculation_result") is not None:
                        with calc_container:
                            st.success(f"💰 Calculation Result: {metadata_result['calculation_result']}")
                    
                    # Generate contextual suggestions
                    suggestions = generate_contextual_prompts(prompt, metadata_result)
                    # Prepend "Generate Insights" for SQL queries that returned data
                    if metadata_result.get("intent_route") == "sql" and metadata_result.get("data") is not None:
                        insights_prompt = f"Generate detailed insights and analysis for: {prompt}"
                        suggestions = [insights_prompt] + suggestions[:3]
                    st.session_state.suggested_prompts = suggestions
                
                st.session_state.messages.append(message_data)
                
                # Save assistant message to PostgreSQL with metadata
                if chat_history and metadata_result and not st.session_state.cancel_generation:
                    db_metadata = {
                        "timestamp": end_time.isoformat(),
                        "tokens": total_tokens,
                        "cost": estimated_cost,
                        "duration": duration,
                        "sql_query": metadata_result.get("sql_query"),
                        "has_visualization": metadata_result.get("visualization") is not None,
                        "data_rows": len(metadata_result["data"]) if metadata_result.get("data") is not None else 0,
                        "calculation_result": metadata_result.get("calculation_result")
                    }
                    chat_history.add_message(
                        session_id=st.session_state.session_id,
                        role="assistant",
                        content=full_response,
                        metadata=db_metadata
                    )
                    
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                error_msg = f"❌ Error processing query: {str(e)}"
                st.error(error_msg)
                with st.expander("🔍 View Error Details"):
                    st.code(error_details)
                
                error_message = {
                    "role": "assistant",
                    "content": error_msg
                }
                st.session_state.messages.append(error_message)
                
                # Save error to chat history
                if chat_history:
                    chat_history.add_message(
                        session_id=st.session_state.session_id,
                        role="assistant",
                        content=error_msg,
                        metadata={"error": True, "timestamp": datetime.now().isoformat()}
                    )
        
        # Rerun to update the chat and show contextual suggestions
        st.rerun()
    
    # Example queries
    with st.expander("💡 Example Queries"):
        st.markdown("""
        **Sales Analysis:**
        - "Show me the top 10 liquor brands by sales revenue"
        - "What are the total sales by month for 2023?"
        - "Which stores have the highest revenue?"
        
        **Geographic Analysis:**
        - "Compare sales across different Iowa counties"
        - "Show me the top 5 cities by liquor sales"
        - "Which county has the highest vodka sales?"
        
        **Product Analysis:**
        - "What are the most popular liquor categories?"
        - "Show me whiskey vs vodka sales comparison"
        - "Which vendors have the highest sales?"
        
        **Business Calculations:**
        - "Calculate the average profit margin"
        - "What's the markup percentage on state bottle cost?"
        - "Calculate sales growth rate year over year"
        """)


if __name__ == "__main__":
    main()
