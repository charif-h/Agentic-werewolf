import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, gameApi } from './api.js';

function respond(status, body) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    statusText: 'status text',
    json: () => (body === undefined ? Promise.reject(new Error('no body')) : Promise.resolve(body)),
  });
}

describe('gameApi', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('creates a game with a JSON body', async () => {
    fetch.mockReturnValue(respond(200, { game_id: 'abc' }));
    const data = await gameApi.createGame(6);
    expect(data.game_id).toBe('abc');
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe('/api/games');
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body)).toEqual({ num_players: 6 });
    expect(options.headers['Content-Type']).toBe('application/json');
  });

  it('uses the game id in the paths and sends no body for plain calls', async () => {
    fetch.mockReturnValue(respond(200, {}));
    await gameApi.getGameState('g1');
    await gameApi.startGame('g1');
    await gameApi.nextPhase('g1');
    await gameApi.getPlayers('g1');
    await gameApi.deleteGame('g1');
    expect(fetch.mock.calls.map(([url, o]) => `${o.method} ${url}`)).toEqual([
      'GET /api/games/g1',
      'POST /api/games/g1/start',
      'POST /api/games/g1/next-phase',
      'GET /api/games/g1/players',
      'DELETE /api/games/g1',
    ]);
    expect(fetch.mock.calls[0][1].body).toBeUndefined();
  });

  it('turns the server detail into the error message', async () => {
    fetch.mockReturnValue(respond(503, { detail: 'Ollama is not running' }));
    await expect(gameApi.createGame()).rejects.toMatchObject({
      name: 'ApiError',
      message: 'Ollama is not running',
      status: 503,
    });
  });

  it('copes with an error without a JSON body', async () => {
    fetch.mockReturnValue(respond(500, undefined));
    await expect(gameApi.getModel()).rejects.toThrow('status text');
  });

  it('reports an unreachable server', async () => {
    fetch.mockRejectedValue(new TypeError('Failed to fetch'));
    const error = await gameApi.getModel().catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.message).toBe('Cannot reach the server');
    expect(error.status).toBe(0);
  });
});
