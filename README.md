# Agentic RAG — BigQuery Chat

A fully agentic RAG application for natural-language data analysis on BigQuery.
The LLM autonomously decides which tools to call, retrieves only the relevant schema chunks via vector search, corrects its own SQL errors, and streams a narrative answer — no hard-coded pipelines.

---

## Architecture

```
User Query
    │
    ▼
Schema RAG  (startup, one-time)
  BigQuery schemas ──► sentence-transformers ──► numpy vector index
  Business rules   ──►   (all-MiniLM-L6-v2)
    │
    │  top-k relevant chunks injected into system prompt
    ▼
LangGraph ReAct Agent
  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐
  │  search_schema  │  │   execute_sql    │  │calculate_metric  │
  │   (RAG step)    │  │  (+ self-fix ×3) │  │  (KPI formulas)  │
  └─────────────────┘  └──────────────────┘  └──────────────────┘
  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐
  │   list_tables   │  │  validate_sql    │  │search_past_queries│
  │                 │  │  (BQ dry-run)    │  │  (pgvector mem)  │
  └─────────────────┘  └──────────────────┘  └──────────────────┘
  Agent decides which tools to call and in what order
    │
    ▼
Streaming Response  (Streamlit)
  ├── Live status:  Retrieving schema... → Running SQL...
  ├── Plotly interactive chart (auto-selected type)
  ├── Raw data table (expandable)
  ├── SQL query viewer (optional — toggle in sidebar)
  └── Narrative answer (streamed word-by-word)
    │
    ▼
pgvector (PostgreSQL)
  Chat History + Semantic Memory
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM (primary) | Ollama local (`gpt-oss:20b` or any tool-capable model) |
| LLM (fallback) | Google Gemini 2.5 Flash |
| Agent framework | LangGraph `create_react_agent` |
| Schema embeddings | `sentence-transformers/all-MiniLM-L6-v2` + numpy cosine similarity |
| Database | Google BigQuery (Iowa Liquor Sales public dataset) |
| Memory store | PostgreSQL + pgvector |
| Visualisation | Plotly (auto chart-type selection) |
| UI | Streamlit |

---

## Project Structure

```
agentic-rag/
├── src/
│   ├── agents/
│   │   ├── orchestrator.py   # LangGraph ReAct agent + streaming response
│   │   └── tools.py          # 6 LangChain tools (RAG, SQL, memory, KPIs)
│   ├── knowledge/
│   │   └── schema_store.py   # Schema vector store (sentence-transformers + numpy)
│   ├── connectors/
│   │   └── bigquery.py       # BigQuery connector + schema introspection
│   ├── config/
│   │   └── manager.py        # YAML client config loader + business calculations
│   ├── llm/
│   │   └── providers.py      # Ollama / Gemini / OpenRouter factory with fallback
│   ├── storage/
│   │   └── chat_history.py   # pgvector chat history + semantic search
│   └── visualization/
│       └── charts.py         # Auto chart-type selection + Plotly rendering
├── configs/
│   ├── client_config.yaml    # Active config (symlink or copy from examples)
│   ├── ecommerce_config.yaml # E-commerce template
│   └── saas_config.yaml      # SaaS template
├── app.py                    # Streamlit chat interface
├── cli.py                    # CLI interface for testing
├── requirements.txt
├── docker-compose.yml        # PostgreSQL + pgvector
└── .env                      # Secrets (never commit)
```

---

## Quick Start

### 1. Prerequisites

- Python 3.11+ (tested on 3.14)
- [Ollama](https://ollama.ai) with a **tool-capable** model

```bash
# Pull a tool-capable model (pick one)
ollama pull gpt-oss:20b        # recommended
ollama pull llama3.1           # alternative
ollama pull mistral-nemo       # alternative
```

> **Important:** `llama3:latest` and `gemma3:4b` do _not_ support tool-calling.
> Use one of the models listed above.

- Google Cloud project with BigQuery enabled (free tier works)

### 2. Install

```bash
git clone <repo> && cd agentic-rag
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure

```bash
cp configs/ecommerce_config.yaml configs/client_config.yaml
```

Create `.env`:

```env
# LLM
LLM_PROVIDER=ollama
LLM_FALLBACK_PROVIDER=gemini
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gpt-oss:20b            # must support tool-calling
GEMINI_API_KEY=your_gemini_key      # optional fallback

# BigQuery
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
BIGQUERY_PROJECT_ID=your-billing-project
BIGQUERY_DATASET=iowa_liquor_sales

# PostgreSQL — skip to disable chat memory
POSTGRES_URL=postgresql://user:pass@localhost:5432/ragdb

# Config
CONFIG_PATH=./configs/client_config.yaml
```

### 4. Start PostgreSQL (optional — for chat memory)

```bash
docker-compose up -d
```

### 5. Run

```bash
make run
# or
streamlit run app.py
```

Open **http://localhost:8501**

---

## The 6 Agent Tools

| Tool | What it does |
|---|---|
| `search_schema` | Embeds the query, retrieves top-k relevant table/column chunks from the vector store — **this is the RAG step** |
| `list_tables` | Returns all tables in the dataset when schema search needs a fallback |
| `validate_sql` | Dry-runs SQL on BigQuery (no charge) to catch errors before executing |
| `execute_sql` | Runs the SQL; auto-corrects errors up to 3× using LLM-generated rewrites |
| `search_past_queries` | Searches pgvector for semantically similar past conversations to reuse proven SQL |
| `calculate_metric` | Evaluates pre-defined business KPI formulas from the YAML config |

---

## Example Queries

```
# Sales analysis
"Show me top 10 liquor brands by total sales revenue"
"Monthly sales trend in 2023 as a line chart"
"Which Iowa counties buy the most whiskey?"

# Business KPIs
"Calculate the average profit margin across all stores"
"What's the markup percentage on state bottle cost?"

# Follow-ups (agent reuses context from prior turns)
"Break that down by category"
"Show the same data as a pie chart"
"Which brands drove the growth?"
```

---

## Client Configuration

```yaml
# configs/client_config.yaml

client_name: "Iowa Liquor Sales Analytics"

data_source:
  type: bigquery
  project_id: bigquery-public-data
  dataset_id: iowa_liquor_sales
  tables: [iowa_liquor_sales]

business_calculations:
  - name: profit_margin
    description: "Gross profit margin percentage"
    formula: "((state_bottle_retail - state_bottle_cost) / state_bottle_retail) * 100"
    parameters: []
    output_format: percentage

domain_context: |
  Iowa Liquor Sales: state-controlled liquor sales records with invoice-level
  detail including store, product, vendor, and geography.

custom_instructions: |
  Always include totals and percentages.
  Prefer monthly aggregations for trend questions.
```

### Adapting to your own dataset

1. Update `BIGQUERY_DATASET` and `BIGQUERY_PROJECT_ID` in `.env`
2. Update `configs/client_config.yaml` with your table names and domain context
3. Restart — the schema vector store re-indexes automatically at startup

---

## LLM Requirements

The ReAct agent requires a model that supports **function/tool calling**.

| Provider | Supported models |
|---|---|
| Ollama (local) | `gpt-oss:20b`, `kimi-k2.5:cloud`, `minimax-m2:cloud`, `llama3.1`, `mistral-nemo` |
| Google Gemini | `gemini-2.5-flash`, `gemini-1.5-pro` (all support tools) |
| OpenRouter | Any model with `tools` in its capabilities list |

Check what your Ollama model supports:
```bash
curl -s http://localhost:11434/api/show -d '{"model":"your-model"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('capabilities',[]))"
```

---

## Troubleshooting

**`NotImplementedError` on startup**
→ Ollama model doesn't support tool-calling. Switch `OLLAMA_MODEL` to `gpt-oss:20b` or `llama3.1`.

**`BigQuery authentication failed`**
→ Run `gcloud auth application-default login` or set `GOOGLE_APPLICATION_CREDENTIALS` to a service account JSON.

**Schema store `warm-up failed`**
→ Check BigQuery credentials and that `BIGQUERY_DATASET` matches an existing dataset in your project.

**`No response generated`**
→ Ollama model timed out. Try a smaller model or increase Ollama's timeout setting.

**`Port 8501 already in use`**
→ `pkill -f "streamlit run"` then `make run`.

---

## Adding New LLM Providers

Extend `src/llm/providers.py`:

```python
class MyProvider(LLMProvider):
    def get_llm(self, **kwargs):
        return MyChatModel(...)

    def get_embeddings(self):
        return MyEmbeddings(...)

LLMFactory._providers["myprovider"] = MyProvider
```

---

## License

MIT — use freely.

---

*Built with LangGraph · LangChain · sentence-transformers · Streamlit · BigQuery · pgvector*
