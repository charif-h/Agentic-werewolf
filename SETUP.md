# Setup Guide

## Prerequisites

Before you begin, ensure you have the following installed:

- Python 3.11 or higher
- Node.js 18 or higher
- npm or yarn
- Docker and Docker Compose (optional but recommended)

## AI API Keys

You need at least one API key from the following providers:

### OpenAI (Recommended)
1. Visit https://platform.openai.com/api-keys
2. Create a new API key
3. Copy the key to your `.env` file

### Google Gemini
1. Visit https://makersuite.google.com/app/apikey
2. Create a new API key
3. Copy the key to your `.env` file

### Mistral AI
1. Visit https://console.mistral.ai/
2. Create an account and generate an API key
3. Copy the key to your `.env` file

## Installation Methods

### Method 1: Docker Compose (Easiest)

1. Clone the repository:
   ```bash
   git clone https://github.com/charif-h/Agentic-werewolf.git
   cd Agentic-werewolf
   ```

2. Create `.env` file from template:
   ```bash
   cp .env.example .env
   ```

3. Edit `.env` and add your API keys:
   ```bash
   nano .env  # or use your preferred editor
   ```

4. Start all services:
   ```bash
   docker-compose up --build
   ```

5. Access the application:
   - Frontend: http://localhost:3000
   - Backend: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Method 2: Manual Installation

#### Backend Setup

1. Navigate to the project root:
   ```bash
   cd Agentic-werewolf
   ```

2. Create a Python virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install Python dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```

4. Create `.env` file:
   ```bash
   cp .env.example .env
   ```

5. Edit `.env` with your API keys

6. Start the backend server:
   ```bash
   uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

#### Frontend Setup

1. Open a new terminal and navigate to frontend:
   ```bash
   cd Agentic-werewolf/frontend
   ```

2. Install Node dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm start
   ```

4. The frontend will open automatically at http://localhost:3000

## Verification

### Backend Verification

1. Visit http://localhost:8000
2. You should see: `{"name":"Werewolves of Millers Hollow API","version":"1.0.0","status":"running"}`

3. Visit http://localhost:8000/docs for API documentation

4. Check available providers:
   ```bash
   curl http://localhost:8000/api/providers
   ```

### Frontend Verification

1. Visit http://localhost:3000
2. You should see the game interface
3. Click "Create New Game" to test the connection

## Common Issues

### Port Already in Use

If port 8000 or 3000 is already in use:

**Backend:**
```bash
# Change the port in the command
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8001
```

**Frontend:**
```bash
# Set PORT environment variable
PORT=3001 npm start
```

### Import Errors

If you get Python import errors:
```bash
# Make sure you're running from the project root
cd Agentic-werewolf
python -m uvicorn backend.main:app --reload
```

### API Key Not Found

Ensure your `.env` file is in the project root (not in the backend folder) and contains valid keys:
```env
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...
MISTRAL_API_KEY=...
AI_PROVIDER=openai
```

### Docker Build Fails

Try cleaning Docker cache:
```bash
docker-compose down
docker system prune -a
docker-compose up --build
```

## Next Steps

Once installation is complete:
1. Read the [README.md](README.md) for gameplay instructions
2. Check [ARCHITECTURE.md](ARCHITECTURE.md) for system design details
3. Start playing and watching the AI agents interact!
