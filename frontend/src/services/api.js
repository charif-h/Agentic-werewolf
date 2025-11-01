import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const gameApi = {
  // Get available AI providers
  getProviders: async () => {
    const response = await api.get('/api/providers');
    return response.data;
  },

  // Create a new game
  createGame: async (numPlayers = 8, aiProvider = null) => {
    const response = await api.post('/api/game/create', {
      num_players: numPlayers,
      ai_provider: aiProvider
    });
    return response.data;
  },

  // Get current game state
  getGameState: async () => {
    const response = await api.get('/api/game/state');
    return response.data;
  },

  // Start the game
  startGame: async () => {
    const response = await api.post('/api/game/start');
    return response.data;
  },

  // Progress to next phase
  nextPhase: async () => {
    const response = await api.post('/api/game/next-phase');
    return response.data;
  },

  // Get all players
  getPlayers: async () => {
    const response = await api.get('/api/players');
    return response.data;
  },
};

export default gameApi;
