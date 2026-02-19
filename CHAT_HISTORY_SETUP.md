# Chat History with PostgreSQL Vector Storage

## Overview

The Agentic RAG application now supports persistent chat history storage using PostgreSQL with the pgvector extension. Conversations are stored as vector embeddings, enabling:

- **Persistent Chat History**: All conversations are saved across sessions
- **Semantic Search**: Find similar past conversations using natural language
- **Session Management**: View, load, and continue past conversations
- **Context Retrieval**: Use past conversations to inform future responses

## Quick Setup

### Option 1: Using Docker (Recommended)

The easiest way to get PostgreSQL with pgvector running:

```bash
# Start PostgreSQL and the application
docker-compose up -d

# Check if services are running
docker-compose ps

# View logs
docker-compose logs -f
```

This automatically sets up:
- PostgreSQL 15 with pgvector extension
- Database: `agentic_rag`
- Tables: `chat_sessions` and `chat_messages`
- Vector embeddings for semantic search

### Option 2: Local PostgreSQL Installation

#### macOS

```bash
# Install PostgreSQL
brew install postgresql@15
brew services start postgresql@15

# Install pgvector
cd /tmp
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector
make
make install

# Create database
createdb agentic_rag

# Enable extension
psql agentic_rag -c "CREATE EXTENSION vector;"
```

#### Ubuntu/Debian

```bash
# Install PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib

# Install pgvector
cd /tmp
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# Create database
sudo -u postgres createdb agentic_rag

# Enable extension
sudo -u postgres psql agentic_rag -c "CREATE EXTENSION vector;"
```

#### Windows

1. Install PostgreSQL from https://www.postgresql.org/download/windows/
2. Install pgvector following instructions at https://github.com/pgvector/pgvector#windows
3. Use pgAdmin or psql to create database and enable extension

### Option 3: Cloud PostgreSQL

You can use managed PostgreSQL services with pgvector:

#### Supabase (Free Tier Available)

1. Create account at https://supabase.com
2. Create new project
3. pgvector is pre-installed!
4. Get connection details from Settings → Database
5. Update `.env` with connection details

#### Neon (Free Tier Available)

1. Create account at https://neon.tech
2. Create new project
3. Enable pgvector extension
4. Get connection string
5. Update `.env`

#### Other Options
- **AWS RDS**: PostgreSQL with pgvector extension
- **Google Cloud SQL**: PostgreSQL with pgvector
- **Azure Database**: PostgreSQL with pgvector
- **DigitalOcean Managed Databases**: PostgreSQL with pgvector

## Configuration

Update your `.env` file with PostgreSQL credentials:

```env
# PostgreSQL Configuration (for chat history storage)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=agentic_rag
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
```

For cloud databases, use the connection details provided:

```env
# Example with Supabase
POSTGRES_HOST=db.xxxxxxxxxxxx.supabase.co
POSTGRES_PORT=5432
POSTGRES_DB=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_supabase_password
```

## Database Schema

The application automatically creates the following tables:

### chat_sessions
```sql
CREATE TABLE chat_sessions (
    session_id VARCHAR(255) PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);
```

### chat_messages
```sql
CREATE TABLE chat_messages (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) REFERENCES chat_sessions(session_id),
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    embedding vector(384),  -- 384-dimensional embeddings from all-MiniLM-L6-v2
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Features

### 1. Automatic History Saving

Every message (user and assistant) is automatically saved to PostgreSQL with:
- Message content
- Vector embedding for semantic search
- Metadata (SQL queries, visualization info, timestamps)
- Session grouping

### 2. Session Management

In the Streamlit sidebar:
- **View Past Sessions**: Browse all saved conversations
- **Load Session**: Continue a previous conversation
- **Session Info**: See message count and timestamps

### 3. Semantic Search

Search your conversation history using natural language:
```
"sales trends" → finds all conversations about sales trends
"county analysis" → finds geographic analysis discussions
"vodka vs whiskey" → finds product comparison conversations
```

The search uses cosine similarity on vector embeddings to find semantically similar messages.

### 4. Context-Aware Responses

Future enhancement: Use past conversations to provide more contextual responses.

## Usage in Code

The `ChatHistoryStore` class can be used programmatically:

```python
from src.storage import ChatHistoryStore

# Initialize
chat_history = ChatHistoryStore()

# Create session
session_id = "my-session-123"
chat_history.create_session(session_id, metadata={"user": "john"})

# Add messages
chat_history.add_message(
    session_id=session_id,
    role="user",
    content="Show me sales trends",
    metadata={"query_type": "analytics"}
)

chat_history.add_message(
    session_id=session_id,
    role="assistant",
    content="Here are the top trends...",
    metadata={"sql_executed": True, "rows_returned": 100}
)

# Get session history
messages = chat_history.get_session_history(session_id)

# Search similar messages
similar = chat_history.search_similar_messages(
    query="sales analysis",
    limit=5,
    similarity_threshold=0.7
)

# Get recent context
context = chat_history.get_recent_context(session_id, limit=5)
```

## Performance Considerations

### Vector Index

The application creates an IVFFlat index for efficient vector similarity search:

```sql
CREATE INDEX chat_messages_embedding_idx 
ON chat_messages USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

For large datasets (>1M messages), consider:
- Increasing `lists` parameter: `WITH (lists = 1000)`
- Using HNSW index (PostgreSQL 15+): `USING hnsw (embedding vector_cosine_ops)`

### Embedding Model

Current: `all-MiniLM-L6-v2` (384 dimensions)
- Fast inference
- Good quality
- Small storage footprint

Alternative models:
- `all-mpnet-base-v2` (768 dimensions) - Better quality, slower
- `paraphrase-MiniLM-L3-v2` (384 dimensions) - Faster inference
- OpenAI embeddings - Higher quality, requires API calls

## Troubleshooting

### Connection Issues

```python
[WARNING] Could not connect to PostgreSQL: connection refused
```

**Solutions:**
1. Check PostgreSQL is running: `pg_isready`
2. Verify connection details in `.env`
3. Check firewall/network settings
4. For Docker: Ensure container is healthy

### pgvector Not Found

```python
ERROR: extension "vector" does not exist
```

**Solutions:**
1. Install pgvector: https://github.com/pgvector/pgvector
2. Verify installation: `psql -c "CREATE EXTENSION vector;"`
3. For RDS/Cloud: Enable extension in console

### Performance Issues

**Slow Searches:**
1. Rebuild vector index: `REINDEX INDEX chat_messages_embedding_idx;`
2. Increase `lists` parameter
3. Consider HNSW index for better performance

**High Storage:**
1. Archive old sessions
2. Clean up test data
3. Use table partitioning for large datasets

## Maintenance

### Backup Chat History

```bash
# Backup database
pg_dump agentic_rag > chat_history_backup.sql

# Backup with compression
pg_dump agentic_rag | gzip > chat_history_backup.sql.gz
```

### Archive Old Sessions

```sql
-- Delete sessions older than 90 days
DELETE FROM chat_messages 
WHERE session_id IN (
    SELECT session_id FROM chat_sessions 
    WHERE created_at < NOW() - INTERVAL '90 days'
);

DELETE FROM chat_sessions 
WHERE created_at < NOW() - INTERVAL '90 days';
```

### Analyze Table Statistics

```sql
-- Update table statistics for better query planning
ANALYZE chat_messages;
ANALYZE chat_sessions;
```

## Cost Considerations

### Storage
- ~400 bytes per message (content + embedding + metadata)
- 1,000 messages ≈ 400 KB
- 1,000,000 messages ≈ 400 MB

### Compute
- Embedding generation: ~10-50ms per message (CPU)
- Vector search: ~1-10ms for 1M vectors with proper indexing

### Cloud Pricing Examples
- **Supabase**: Free tier includes 500MB database
- **Neon**: Free tier includes 512MB storage
- **AWS RDS**: ~$15/month for small instance
- **DigitalOcean**: $15/month managed database

## Future Enhancements

- [ ] Conversation summarization
- [ ] Multi-user support with authentication
- [ ] Export conversations to PDF/JSON
- [ ] Conversation analytics dashboard
- [ ] RAG over past conversations
- [ ] Automatic context injection from similar past queries
- [ ] Conversation tagging and categorization

## Security

### Best Practices

1. **Use strong passwords** in production
2. **Enable SSL/TLS** for database connections
3. **Restrict network access** (firewall rules)
4. **Regular backups** of chat history
5. **Encrypt sensitive metadata** if needed

### Example: SSL Connection

```env
POSTGRES_SSLMODE=require
POSTGRES_SSLROOTCERT=/path/to/ca-certificate.crt
```

## Support

- GitHub Issues: [Report bugs or request features](https://github.com/yourusername/agentic-rag/issues)
- Documentation: [Full docs](./README.md)
- pgvector: https://github.com/pgvector/pgvector

## License

Same as the main project.
