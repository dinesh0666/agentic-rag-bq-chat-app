.PHONY: help install setup run cli test docker-build docker-up docker-down clean

# Default target
help:
	@echo "🤖 Agentic RAG - Available Commands"
	@echo "=================================="
	@echo "make install      - Install dependencies"
	@echo "make setup        - Run complete setup (venv + install + config)"
	@echo "make run          - Run Streamlit app"
	@echo "make cli          - Run interactive CLI"
	@echo "make test         - Run tests"
	@echo "make docker-build - Build Docker image"
	@echo "make docker-up    - Start Docker containers"
	@echo "make docker-down  - Stop Docker containers"
	@echo "make clean        - Clean up temporary files"
	@echo ""

# Install dependencies
install:
	@echo "📚 Installing dependencies..."
	pip install -r requirements.txt
	@echo "✅ Dependencies installed"

# Complete setup
setup:
	@echo "🚀 Running setup script..."
	chmod +x setup.sh
	./setup.sh

# Run Streamlit app
run:
	@echo "🌐 Starting Streamlit app..."
	.venv/bin/streamlit run app.py

# Run CLI in interactive mode
cli:
	@echo "💬 Starting interactive CLI..."
	.venv/bin/python cli.py --interactive

# Run with specific config
run-ecommerce:
	@echo "🛒 Running with e-commerce config..."
	CONFIG_PATH=./configs/ecommerce_config.yaml .venv/bin/streamlit run app.py

run-saas:
	@echo "💼 Running with SaaS config..."
	CONFIG_PATH=./configs/saas_config.yaml .venv/bin/streamlit run app.py

# Run tests
test:
	@echo "🧪 Running tests..."
	pytest tests/ -v

# Docker commands
docker-build:
	@echo "🐳 Building Docker image..."
	docker build -t agentic-rag:latest .

docker-up:
	@echo "🐳 Starting Docker containers..."
	docker-compose up -d
	@echo "✅ Application running at http://localhost:8501"

docker-down:
	@echo "🐳 Stopping Docker containers..."
	docker-compose down

docker-logs:
	@echo "📋 Showing Docker logs..."
	docker-compose logs -f

# Development
dev:
	@echo "👨‍💻 Starting in development mode..."
	DEBUG_MODE=true streamlit run app.py

# Lint and format
lint:
	@echo "🔍 Linting code..."
	flake8 src/ --max-line-length=120 --exclude=__pycache__
	pylint src/ --max-line-length=120

format:
	@echo "✨ Formatting code..."
	black src/ tests/ app.py cli.py
	isort src/ tests/ app.py cli.py

# Clean up
clean:
	@echo "🧹 Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf logs/*.log
	@echo "✅ Cleanup complete"

# Quick start for new users
quickstart:
	@echo "🚀 Quick Start Setup"
	@echo "==================="
	@make setup
	@echo ""
	@echo "Next steps:"
	@echo "1. Edit .env file with your credentials"
	@echo "2. Choose a config: make run-ecommerce OR make run-saas"
	@echo "3. Or run: make run"
