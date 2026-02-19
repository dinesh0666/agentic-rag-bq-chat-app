# Deployment Guide

## 🚀 Deployment Options

This guide covers deploying your Agentic RAG application to production.

## Option 1: Google Cloud Run (Recommended)

### Prerequisites
- Google Cloud Project
- gcloud CLI installed
- Docker installed

### Steps

1. **Create Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8080

# Run the application
CMD streamlit run app.py --server.port=8080 --server.address=0.0.0.0
```

2. **Build and Deploy**

```bash
# Set your project ID
export PROJECT_ID=your-project-id
export REGION=us-central1

# Build the container
gcloud builds submit --tag gcr.io/$PROJECT_ID/agentic-rag

# Deploy to Cloud Run
gcloud run deploy agentic-rag \
  --image gcr.io/$PROJECT_ID/agentic-rag \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars="LLM_PROVIDER=gemini,CONFIG_PATH=/app/configs/client_config.yaml" \
  --set-secrets="GEMINI_API_KEY=gemini-key:latest,BIGQUERY_PROJECT_ID=bq-project:latest"
```

3. **Set up Secrets**

```bash
# Create secrets in Secret Manager
echo -n "your-gemini-api-key" | gcloud secrets create gemini-key --data-file=-
echo -n "your-project-id" | gcloud secrets create bq-project --data-file=-
```

## Option 2: Docker Compose (Local/VM)

### docker-compose.yml

```yaml
version: '3.8'

services:
  agentic-rag:
    build: .
    ports:
      - "8501:8501"
    environment:
      - LLM_PROVIDER=${LLM_PROVIDER}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - BIGQUERY_PROJECT_ID=${BIGQUERY_PROJECT_ID}
      - BIGQUERY_DATASET=${BIGQUERY_DATASET}
      - CONFIG_PATH=/app/configs/client_config.yaml
    volumes:
      - ./configs:/app/configs
      - ./chroma_db:/app/chroma_db
      - ${GOOGLE_APPLICATION_CREDENTIALS}:/app/service-account.json
    env_file:
      - .env
    command: streamlit run app.py
```

### Deploy

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## Option 3: AWS ECS/Fargate

### Task Definition (JSON)

```json
{
  "family": "agentic-rag",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "agentic-rag",
      "image": "your-ecr-repo/agentic-rag:latest",
      "portMappings": [
        {
          "containerPort": 8501,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "LLM_PROVIDER",
          "value": "gemini"
        }
      ],
      "secrets": [
        {
          "name": "GEMINI_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:gemini-key"
        }
      ]
    }
  ]
}
```

## Option 4: Kubernetes

### Deployment YAML

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agentic-rag
spec:
  replicas: 2
  selector:
    matchLabels:
      app: agentic-rag
  template:
    metadata:
      labels:
        app: agentic-rag
    spec:
      containers:
      - name: agentic-rag
        image: your-registry/agentic-rag:latest
        ports:
        - containerPort: 8501
        env:
        - name: LLM_PROVIDER
          value: "gemini"
        - name: GEMINI_API_KEY
          valueFrom:
            secretKeyRef:
              name: agentic-rag-secrets
              key: gemini-api-key
        volumeMounts:
        - name: config
          mountPath: /app/configs
      volumes:
      - name: config
        configMap:
          name: client-config

---
apiVersion: v1
kind: Service
metadata:
  name: agentic-rag
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8501
  selector:
    app: agentic-rag
```

## Security Best Practices

### 1. API Key Management

```bash
# Use environment variables, never hardcode
# Use secret management services:
# - Google Secret Manager
# - AWS Secrets Manager
# - Azure Key Vault
# - HashiCorp Vault
```

### 2. Network Security

```yaml
# Cloud Run - VPC Connector for private BigQuery access
# ECS - Security Groups
# Kubernetes - Network Policies
```

### 3. Authentication

Add authentication to your Streamlit app:

```python
# In app.py
import streamlit_authenticator as stauth

# Add authentication
authenticator = stauth.Authenticate(
    credentials,
    'cookie_name',
    'signature_key',
    cookie_expiry_days=30
)

name, authentication_status, username = authenticator.login('Login', 'main')

if authentication_status:
    # Show app
    main()
elif authentication_status == False:
    st.error('Username/password is incorrect')
```

## Performance Optimization

### 1. Caching

```python
# Already implemented in app.py
@st.cache_resource
def initialize_system():
    ...
```

### 2. Connection Pooling

For BigQuery, use connection pooling in production:

```python
# In src/connectors/bigquery.py
from google.cloud.bigquery import Client
from google.cloud.bigquery_storage import BigQueryReadClient

# Use storage API for faster reads
storage_client = BigQueryReadClient()
```

### 3. Query Optimization

- Add query result caching
- Implement query cost limits
- Use BigQuery partitioned tables

## Monitoring

### 1. Logging

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
```

### 2. Metrics

Track key metrics:
- Query response time
- LLM token usage
- BigQuery bytes processed
- Error rates
- User sessions

### 3. Alerts

Set up alerts for:
- High error rates
- Slow queries
- API quota exceeded
- Service downtime

## Scaling Considerations

### Horizontal Scaling

```bash
# Cloud Run - auto-scales
# ECS - set desired count
# Kubernetes - use HPA

kubectl autoscale deployment agentic-rag \
  --cpu-percent=70 \
  --min=2 \
  --max=10
```

### Vertical Scaling

Adjust resources based on load:
- CPU: 1-4 vCPU
- Memory: 2-8 GB
- Consider LLM API rate limits

## Cost Optimization

1. **LLM Costs**
   - Use cheaper models for simple queries
   - Implement token usage tracking
   - Cache responses

2. **BigQuery Costs**
   - Implement query result caching
   - Set query byte limits
   - Use partitioned/clustered tables

3. **Infrastructure Costs**
   - Use spot instances (if applicable)
   - Auto-scaling based on usage
   - Schedule scaling down during off-hours

## Backup and Recovery

```bash
# Backup configurations
tar -czf backup-$(date +%Y%m%d).tar.gz configs/ .env

# Database backup (if using local storage)
# BigQuery - automatic backups
```

## Multi-Client Deployment

For serving multiple clients:

1. **Separate Deployments**
   - Deploy separate instances per client
   - Isolated configurations and databases

2. **Multi-Tenant**
   - Single deployment
   - Client selection in UI
   - Load configs dynamically

```python
# In app.py
client_name = st.sidebar.selectbox("Select Client", available_clients)
config_manager.load_config(f"configs/{client_name}_config.yaml")
```

## CI/CD Pipeline

### GitHub Actions Example

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    
    - name: Setup Cloud SDK
      uses: google-github-actions/setup-gcloud@v0
    
    - name: Build and Deploy
      run: |
        gcloud builds submit --tag gcr.io/$PROJECT_ID/agentic-rag
        gcloud run deploy agentic-rag \
          --image gcr.io/$PROJECT_ID/agentic-rag \
          --platform managed
```

## Health Checks

Add health check endpoint:

```python
# In app.py
@st.cache_data(ttl=60)
def health_check():
    try:
        # Check BigQuery connection
        bq_connector.client.query("SELECT 1").result()
        return {"status": "healthy"}
    except:
        return {"status": "unhealthy"}
```

---

For more details, see the main [README.md](README.md)
