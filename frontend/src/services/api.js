// Talks to the backend. In development and behind nginx the paths are relative (/api/...),
// so the page and the API share one origin. VITE_API_URL points somewhere else if needed.
const API_BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request(method, path, body) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (err) {
    throw new ApiError('Cannot reach the server', 0);
  }
  let data = null;
  try {
    data = await response.json();
  } catch (err) {
    // an empty or non-JSON body is fine for errors
  }
  if (!response.ok) {
    const detail = data && typeof data.detail === 'string' ? data.detail : response.statusText;
    throw new ApiError(detail || `Request failed (${response.status})`, response.status);
  }
  return data;
}

export const gameApi = {
  // Local model status: { model, host, reachable, installed, size_bytes }
  getModel: () => request('GET', '/api/model'),

  // Create a new game; the response contains its game_id
  createGame: (numPlayers = 8) => request('POST', '/api/games', { num_players: numPlayers }),

  getGameState: (gameId) => request('GET', `/api/games/${gameId}`),
  startGame: (gameId) => request('POST', `/api/games/${gameId}/start`),
  nextPhase: (gameId) => request('POST', `/api/games/${gameId}/next-phase`),
  getPlayers: (gameId) => request('GET', `/api/games/${gameId}/players`),
  deleteGame: (gameId) => request('DELETE', `/api/games/${gameId}`),
};

export default gameApi;
