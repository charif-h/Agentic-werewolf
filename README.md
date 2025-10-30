# 🐺 Agentic Werewolf 🌙

An AI-powered recreation of "The Werewolves of Millers Hollow" featuring 25 autonomous AI agents (1 Game Master + 24 Players) with unique personalities based on the 16 personality types (MBTI).

## 🎮 Features

- **25 AI Agents**: 1 Game Master and 24 Players, each with distinct personalities
- **Personality System**: Characters based on the 16 personality types (INTJ, ENFP, etc.)
- **Randomly Generated Profiles**: Each player has a unique name, sex, age, and personality
- **Multi-LLM Support**: Compatible with OpenAI GPT-4, Google Gemini, and Mistral AI
- **Real-time Web Interface**: Watch the game unfold with a modern React frontend
- **Full Game Implementation**: Complete Werewolves of Millers Hollow rules and mechanics
- **WebSocket Support**: Real-time updates during gameplay

## 🏗️ Technology Stack

### Backend
- **Python 3.11+** with FastAPI
- **LangChain** for AI agent orchestration
- **Multiple AI Providers**:
  - OpenAI (GPT-4)
  - Google Gemini
  - Mistral AI
- **Uvicorn** ASGI server
- **WebSocket** for real-time communication

### Frontend
- **React 18** with modern hooks
- **Axios** for API communication
- **Socket.IO Client** for WebSocket
- **Responsive CSS** with modern design

### DevOps
- **Docker** and **Docker Compose** for containerization
- **Nginx** for frontend serving and reverse proxy

## 📋 Prerequisites

- Python 3.11 or higher
- Node.js 18 or higher
- Docker and Docker Compose (optional)
- API keys for at least one of:
  - OpenAI API key
  - Google AI (Gemini) API key
  - Mistral AI API key

## 🚀 Quick Start

### Option 1: Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/charif-h/Agentic-werewolf.git
   cd Agentic-werewolf
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your API keys:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   GOOGLE_API_KEY=your_gemini_api_key_here
   MISTRAL_API_KEY=your_mistral_api_key_here
   AI_PROVIDER=openai  # or gemini, mistral
   ```

3. **Start the application**
   ```bash
   docker-compose up --build
   ```

4. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Option 2: Manual Setup

#### Backend Setup

1. **Install Python dependencies**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Set up environment variables**
   ```bash
   cp ../.env.example ../.env
   # Edit .env with your API keys
   ```

3. **Run the backend server**
   ```bash
   cd ..
   python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

#### Frontend Setup

1. **Install Node dependencies**
   ```bash
   cd frontend
   npm install
   ```

2. **Start the development server**
   ```bash
   npm start
   ```

3. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000

## 🎯 How to Play

1. **Create a New Game**: Click "Create New Game (24 Players)" to initialize the game with 24 AI agents
2. **Start the Game**: Once created, click "Start Game" to begin the first night phase
3. **Progress Through Phases**: Click "Next Phase" to advance through:
   - **Night**: Werewolves and special roles perform their actions
   - **Day**: Players discover who died during the night
   - **Discussion**: Players debate and share suspicions
   - **Voting**: Players vote to eliminate a suspect
4. **Watch the Drama Unfold**: Observe as AI agents with different personalities interact and strategize
5. **Game End**: The game concludes when either all werewolves are eliminated (villagers win) or werewolves equal/outnumber villagers (werewolves win)

## 🃏 Game Roles

- **Werewolves** (4): Kill villagers each night
- **Villagers** (15): Try to identify and eliminate werewolves
- **Seer** (1): Can reveal one player's identity each night
- **Witch** (1): Has two potions - one to save, one to kill
- **Hunter** (1): When killed, can eliminate another player
- **Cupid** (1): Makes two players fall in love on the first night
- **Guard** (1): Can protect one player each night

## 🧠 Personality System

Each player is assigned one of 16 personality types that influence their behavior:

**Analysts**: INTJ, INTP, ENTJ, ENTP
**Diplomats**: INFJ, INFP, ENFJ, ENFP
**Sentinels**: ISTJ, ISFJ, ESTJ, ESFJ
**Explorers**: ISTP, ISFP, ESTP, ESFP

Personalities affect:
- Communication style (formal/casual, aggressive/gentle)
- Decision-making approach (logical/emotional)
- Trust-building and suspicion patterns
- Voting behavior

## 🔧 Configuration

### AI Provider Selection

You can choose which AI provider to use by setting the `AI_PROVIDER` environment variable:

```env
AI_PROVIDER=openai    # For GPT-4
AI_PROVIDER=gemini    # For Google Gemini
AI_PROVIDER=mistral   # For Mistral AI
```

### Adjusting Player Count

Modify the number of players when creating a game via the API:

```bash
curl -X POST "http://localhost:8000/api/game/create?num_players=12"
```

## 📚 API Documentation

Once the backend is running, visit http://localhost:8000/docs for interactive API documentation.

### Key Endpoints

- `POST /api/game/create` - Create a new game
- `GET /api/game/state` - Get current game state
- `POST /api/game/start` - Start the game
- `POST /api/game/next-phase` - Progress to next phase
- `GET /api/players` - Get all player profiles
- `GET /api/providers` - Get available AI providers

## 🛠️ Development

### Project Structure

```
Agentic-werewolf/
├── backend/
│   ├── agents/           # AI agent implementations
│   │   ├── ai_provider.py      # LLM provider factory
│   │   ├── game_master_agent.py # Game master AI
│   │   ├── player_agent.py      # Player AI
│   │   └── profile_generator.py # Player profile generator
│   ├── game/             # Game logic
│   │   └── game_logic.py       # Core game mechanics
│   ├── models/           # Data models
│   │   └── game_models.py      # Pydantic models
│   ├── main.py           # FastAPI application
│   └── requirements.txt  # Python dependencies
├── frontend/
│   ├── public/           # Static files
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── services/     # API services
│   │   ├── App.js        # Main React component
│   │   └── App.css       # Styles
│   └── package.json      # Node dependencies
├── docker-compose.yml    # Docker orchestration
├── Dockerfile.backend    # Backend container
├── Dockerfile.frontend   # Frontend container
└── README.md            # This file
```

### Running Tests

```bash
# Backend tests (to be implemented)
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

This project is open source and available under the MIT License.

## 🙏 Acknowledgments

- Inspired by "The Werewolves of Millers Hollow" board game
- Built with LangChain for multi-LLM support
- Personality system based on the Myers-Briggs Type Indicator (MBTI)

## 🐛 Troubleshooting

### "No API key found" error
Ensure you've set up the `.env` file with valid API keys for at least one provider.

### Backend won't start
Check that port 8000 is available and Python 3.11+ is installed.

### Frontend won't connect
Verify the backend is running and the `REACT_APP_API_URL` points to the correct backend URL.

### Docker issues
Try `docker-compose down` followed by `docker-compose up --build` to rebuild containers.

## 📧 Contact

For questions or support, please open an issue on GitHub.
