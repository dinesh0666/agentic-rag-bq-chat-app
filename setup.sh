#!/bin/bash

# Setup script for Agentic RAG application

set -e

echo "🚀 Setting up Agentic RAG Application"
echo "======================================"
echo ""

# Check Python version
echo "📋 Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.9"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3,9) else 1)"; then
    echo "❌ Python 3.9+ is required. Found: $python_version"
    exit 1
fi
echo "✅ Python version: $python_version"
echo ""

# Create virtual environment
echo "📦 Creating virtual environment..."
if [ -d "venv" ]; then
    echo "⚠️  Virtual environment already exists. Skipping creation."
else
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi
echo ""

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate || . venv/bin/activate
echo "✅ Virtual environment activated"
echo ""

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip -q
echo "✅ pip upgraded"
echo ""

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt -q
echo "✅ Dependencies installed"
echo ""

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p configs
mkdir -p chroma_db
mkdir -p logs
echo "✅ Directories created"
echo ""

# Setup environment file
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env file created"
    echo "⚠️  Please edit .env and add your API keys and credentials"
else
    echo "ℹ️  .env file already exists. Skipping."
fi
echo ""

# Check for config file
if [ ! -f "configs/client_config.yaml" ]; then
    echo "⚠️  No client configuration found."
    echo "📝 You can use one of the example configs:"
    echo "   cp configs/ecommerce_config.yaml configs/client_config.yaml"
    echo "   cp configs/saas_config.yaml configs/client_config.yaml"
else
    echo "✅ Client configuration found"
fi
echo ""

echo "======================================"
echo "✨ Setup Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your credentials:"
echo "   nano .env"
echo ""
echo "2. Choose or create a client configuration:"
echo "   cp configs/ecommerce_config.yaml configs/client_config.yaml"
echo ""
echo "3. Run the application:"
echo "   source venv/bin/activate  # If not already activated"
echo "   streamlit run app.py"
echo ""
echo "Or use the CLI:"
echo "   python cli.py --interactive"
echo ""
echo "For more information, see README.md"
echo ""
