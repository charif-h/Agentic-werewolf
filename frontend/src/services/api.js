import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const gameApi = {
  // Local model status: { model, host, reachable, installed, size_bytes }
  getModel: async () => {
    const response = await api.get('/api/model');
    return response.data;
  },

  // Create a new game; the response contains its game_id
  createGame: async (numPlayers = 8) => {
    const response = await api.post('/api/games', {
      num_players: numPlayers
    });
    return response.data;
  },

  // Get current game state
  getGameState: async (gameId) => {
    const response = await api.get(`/api/games/${gameId}`);
    return response.data;
  },

  // Start the game
  startGame: async (gameId) => {
    const response = await api.post(`/api/games/${gameId}/start`);
    return response.data;
  },

  // Progress to next phase
  nextPhase: async (gameId) => {
    const response = await api.post(`/api/games/${gameId}/next-phase`);
    return response.data;
  },

  // Get all players
  getPlayers: async (gameId) => {
    const response = await api.get(`/api/games/${gameId}/players`);
    return response.data;
  },

  // Delete a game
  deleteGame: async (gameId) => {
    const response = await api.delete(`/api/games/${gameId}`);
    return response.data;
  },
};

export default gameApi;
