# Ollama Setup Guide

This application uses Ollama as a fallback LLM when the primary provider (Gemini) hits rate limits or quota exhaustion.

## Installation

### macOS
```bash
# Install Ollama
brew install ollama

# Start Ollama service
ollama serve
```

### Linux
```bash
# Download and install
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama service
ollama serve
```

### Windows
Download from: https://ollama.com/download

## Download Models

```bash
# Download Llama 3.2 (recommended, 2GB)
ollama pull llama3.2

# Or other models:
ollama pull llama2           # 3.8GB
ollama pull mistral          # 4.1GB
ollama pull codellama        # 3.8GB
ollama pull phi              # 1.3GB (smaller, faster)
```

## Verify Installation

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Test with a simple query
ollama run llama3.2 "Hello, how are you?"
```

## Configuration

In your `.env` file:

```bash
# Primary LLM (will try this first)
LLM_PROVIDER=gemini

# Fallback LLM (uses this when primary fails)
LLM_FALLBACK_PROVIDER=ollama

# Ollama configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

## Supported Models

- **llama3.2** (Recommended): 2GB, fast and accurate
- **llama2**: 3.8GB, good general purpose
- **mistral**: 4.1GB, excellent for coding and analysis
- **phi**: 1.3GB, smaller and faster
- **codellama**: 3.8GB, optimized for code

## How Fallback Works

1. Application tries to use primary LLM (Gemini)
2. If Gemini returns `RESOURCE_EXHAUSTED` or quota errors, automatically switches to Ollama
3. Shows warning: "*⚠️ Using OLLAMA due to rate limits*"
4. Continues processing without interruption

## Performance

- **Gemini**: Cloud-based, fast, may hit rate limits
- **Ollama**: Local, no rate limits, requires local resources

## Troubleshooting

### Ollama not responding
```bash
# Restart Ollama
pkill ollama
ollama serve
```

### Model not found
```bash
# List installed models
ollama list

# Pull the model
ollama pull llama3.2
```

### Port already in use
```bash
# Check what's using port 11434
lsof -i :11434

# Or change port in .env
OLLAMA_BASE_URL=http://localhost:11435
```

## Resources

- Official Website: https://ollama.com
- GitHub: https://github.com/ollama/ollama
- Model Library: https://ollama.com/library
