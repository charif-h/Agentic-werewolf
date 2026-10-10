#!/bin/bash

# Quick Start Script for Werewolves of Millers Hollow
# This script helps you get started quickly

set -e

echo "======================================"
echo "Werewolves of Millers Hollow Setup"
echo "======================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found!"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "✓ .env file created"
    echo ""
    echo "ℹ️  No API key is needed: the game uses a local model through Ollama."
    echo "   Install Ollama (https://ollama.com), then run: ollama pull gemma3:4b"
    echo ""
fi

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Found Python $python_version"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -q --upgrade pip
pip install -q -r backend/requirements.txt
echo "✓ Python dependencies installed"
echo ""

# Check Node.js
if command -v node &> /dev/null; then
    node_version=$(node --version)
    echo "✓ Found Node.js $node_version"
    
    # Install frontend dependencies
    if [ ! -d "frontend/node_modules" ]; then
        echo "Installing frontend dependencies..."
        cd frontend
        npm install --silent
        cd ..
        echo "✓ Frontend dependencies installed"
    else
        echo "✓ Frontend dependencies already installed"
    fi
else
    echo "⚠️  Node.js not found. Frontend will not be available."
    echo "   Install Node.js from https://nodejs.org/"
fi

echo ""
echo "======================================"
echo "Setup Complete!"
echo "======================================"
echo ""
echo "To start the application:"
echo ""
echo "Option 1: Docker (Recommended)"
echo "  docker compose up --build        # starts Ollama and downloads the model (about 3.4 GB)"
echo "  docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build   # with an NVIDIA GPU"
echo ""
echo "Option 2: Manual (Ollama installed on this machine)"
echo "  scripts/pull_model.sh            # downloads the model"
echo "  Terminal 1 (Backend):"
echo "    source venv/bin/activate"
echo "    uvicorn backend.main:app --reload"
echo ""
echo "  Terminal 2 (Frontend):"
echo "    cd frontend"
echo "    npm run dev"
echo ""
echo "Then visit: http://localhost:3000"
echo ""
