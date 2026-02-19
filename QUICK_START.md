# 🚀 Quick Start Guide

Get up and running with Agentic RAG in 5 minutes!

## Prerequisites Checklist

- [ ] Python 3.9 or higher installed
- [ ] Google Cloud account with BigQuery access
- [ ] API key from Gemini or OpenRouter
- [ ] Service account JSON file for BigQuery

## Step-by-Step Setup

### 1️⃣ Clone and Setup (1 minute)

```bash
# Navigate to the project directory
cd agentic-rag

# Run the setup script
make setup
# OR
chmod +x setup.sh && ./setup.sh
```

This will:
- Create a virtual environment
- Install all dependencies
- Create necessary directories
- Copy .env template

### 2️⃣ Configure Environment (2 minutes)

Edit the `.env` file:

```bash
# Open the .env file
nano .env  # or use your preferred editor
```

Fill in your credentials:

```env
# Pick ONE LLM provider
LLM_PROVIDER=gemini

# For Gemini (recommended)
GEMINI_API_KEY=AIzaSy...your-key-here

# OR for OpenRouter
OPENROUTER_API_KEY=sk-or-v1-...your-key-here

# BigQuery settings
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
BIGQUERY_PROJECT_ID=your-project-id
BIGQUERY_DATASET=your-dataset-name
```

**Where to get API keys:**
- **Gemini**: https://makersuite.google.com/app/apikey
- **OpenRouter**: https://openrouter.ai/keys

### 3️⃣ Choose Your Configuration (1 minute)

Pick a pre-made config or create your own:

**Option A: E-commerce Business**
```bash
cp configs/ecommerce_config.yaml configs/client_config.yaml
```

**Option B: SaaS Business**
```bash
cp configs/saas_config.yaml configs/client_config.yaml
```

**Option C: Custom Configuration**
See the [Configuration Guide](#configuration-guide) below.

### 4️⃣ Run the Application (30 seconds)

```bash
# Activate virtual environment (if not already active)
source venv/bin/activate  # Mac/Linux
# OR
venv\Scripts\activate     # Windows

# Start the app
make run
# OR
streamlit run app.py
```

Your browser will automatically open to `http://localhost:8501` 🎉

## 🎮 Using the Application

### Chat Interface

1. **Type your question** in the chat input
2. The AI agent will:
   - Understand your intent
   - Generate SQL if needed
   - Query BigQuery
   - Perform calculations
   - Create visualizations
   - Give you a clear answer

### Example Questions

Try these queries:

```
📊 Data Queries:
- "Show me the top 10 customers by revenue"
- "What's the sales trend for the last 6 months?"
- "Give me a breakdown of orders by product category"
- "How many new customers did we get last month?"

🧮 Calculations:
- "Calculate the customer lifetime value"
- "What's our monthly recurring revenue?"
- "Show me the customer churn rate"
- "Calculate inventory turnover"

📈 Analysis:
- "Compare Q1 vs Q2 revenue"
- "What are our best-selling products?"
- "Show me user engagement metrics"
```

### Sidebar Features

- **📊 Available Tables**: See all your BigQuery tables
- **🧮 Business Calculations**: View configured calculations
- **Show SQL Queries**: Enable to see generated SQL
- **Show Raw Data**: Toggle data table display
- **Clear Chat History**: Start fresh

## 🛠️ Configuration Guide

### Creating Custom Client Config

Create a new YAML file in `configs/`:

```yaml
client_name: "My Business"

data_source:
  type: "bigquery"
  project_id: "my-project"
  dataset_id: "my_dataset"
  tables:
    - "customers"
    - "orders"
    - "products"

business_calculations:
  - name: "my_metric"
    description: "Description of what this calculates"
    formula: "revenue / customers"
    parameters:
      - "revenue"
      - "customers"
    output_format: "number"  # currency, percentage, ratio, number

visualization:
  default_chart_type: "bar"
  color_scheme: "plotly"
  enable_interactive: true

custom_instructions: |
  Any specific instructions for the AI agent
  about how to handle your data.

domain_context: |
  Information about your business domain
  that helps the agent understand your data.
```

### Business Calculation Examples

```yaml
# Profit Margin
- name: "profit_margin"
  description: "Calculate profit margin percentage"
  formula: "((revenue - cost) / revenue) * 100"
  parameters: ["revenue", "cost"]
  output_format: "percentage"

# Growth Rate
- name: "growth_rate"
  description: "Calculate period over period growth"
  formula: "((current - previous) / previous) * 100"
  parameters: ["current", "previous"]
  output_format: "percentage"

# Average Deal Size
- name: "avg_deal_size"
  description: "Average deal size"
  formula: "total_revenue / num_deals"
  parameters: ["total_revenue", "num_deals"]
  output_format: "currency"
```

## 🐳 Docker Quick Start (Alternative)

If you prefer Docker:

```bash
# 1. Edit .env file with your credentials
nano .env

# 2. Build and run
make docker-up

# 3. Access at http://localhost:8501

# View logs
make docker-logs

# Stop containers
make docker-down
```

## 💬 CLI Mode

For terminal lovers:

```bash
# Interactive mode
make cli

# Or single query
python cli.py "Show me the top customers"

# With specific config
python cli.py --config configs/ecommerce_config.yaml "Show sales trends"
```

## 🆘 Troubleshooting

### Issue: Import errors or module not found

```bash
# Make sure you're in the virtual environment
source venv/bin/activate

# Reinstall dependencies
make install
```

### Issue: BigQuery authentication failed

```bash
# Verify your service account file exists
ls -la /path/to/service-account.json

# Test BigQuery access
python -c "from google.cloud import bigquery; client = bigquery.Client(); print('✅ Connection successful')"
```

### Issue: LLM API errors

```bash
# Verify your API key is set
echo $GEMINI_API_KEY

# Test the API
python -c "import os; from src.llm import LLMFactory; llm = LLMFactory.get_llm(); print('✅ LLM working')"
```

### Issue: Configuration not loading

```bash
# Check .env file
cat .env | grep CONFIG_PATH

# Verify config file exists
ls -la configs/client_config.yaml

# Test loading
python -c "from src.config import ConfigManager; cm = ConfigManager(); print('✅ Config loaded:', cm.config.client_name)"
```

## 📚 Next Steps

1. **Customize**: Edit `configs/client_config.yaml` for your business
2. **Explore**: Try different types of questions
3. **Extend**: Add custom calculations or visualization types
4. **Deploy**: See [DEPLOYMENT.md](DEPLOYMENT.md) for production deployment

## 🎯 Common Use Cases

### Use Case 1: Sales Analytics
```
"Show me monthly revenue trends"
"What are the top performing products?"
"Calculate average order value"
```

### Use Case 2: Customer Insights
```
"Who are our highest value customers?"
"Calculate customer churn rate"
"Show customer acquisition trends"
```

### Use Case 3: Operational Metrics
```
"What's our inventory turnover?"
"Show order fulfillment times"
"Calculate operational efficiency"
```

## 🌟 Pro Tips

1. **Be Specific**: More context = better results
2. **Use Calculations**: Define common metrics in your config
3. **Check SQL**: Enable "Show SQL" to verify queries
4. **Iterate**: Refine your questions based on results
5. **Context Matters**: The agent remembers conversation context

## 📖 Additional Resources

- [README.md](README.md) - Full documentation
- [DEPLOYMENT.md](DEPLOYMENT.md) - Production deployment guide
- [configs/ecommerce_config.yaml](configs/ecommerce_config.yaml) - E-commerce example
- [configs/saas_config.yaml](configs/saas_config.yaml) - SaaS example

## 🤝 Need Help?

1. Check the [troubleshooting section](#-troubleshooting)
2. Review example configs in `configs/`
3. Verify all environment variables are set
4. Check logs in `logs/` directory

---

**Ready to chat with your data! 🚀**

For detailed documentation, see the main [README.md](README.md)
