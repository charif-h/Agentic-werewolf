import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App.jsx';

// The page talks to a fake live connection that the tests control
const sockets = [];
vi.mock('./services/socket.js', () => ({
  createGameSocket: (gameId, handlers) => {
    const socket = { gameId, handlers, closed: false, close() { this.closed = true; } };
    sockets.push(socket);
    return socket;
  },
}));

const PLAYERS = [
  { id: 'p1', name: 'Ann', sex: 'female', age: 30, personality: 'INTJ', status: 'alive', role: null },
  { id: 'p2', name: 'Bob', sex: 'male', age: 41, personality: 'ENFP', status: 'dead', role: 'werewolf' },
];

let serverGame;
let calls;

function json(body, status = 200) {
  return Promise.resolve({ ok: status < 400, status, statusText: '', json: () => Promise.resolve(body) });
}

function installServer() {
  serverGame = { phase: 'setup', day_number: 0, players: PLAYERS, game_log: ['[GAME MASTER] Welcome'], llm: { calls: 0, skipped_turns: 0 } };
  calls = [];
  vi.stubGlobal('fetch', vi.fn((url, options = {}) => {
    const method = options.method || 'GET';
    calls.push(`${method} ${url}`);
    if (url === '/api/model') return json({ model: 'gemma3:4b', reachable: true, installed: true, loaded: true, vram_bytes: 2.9e9 });
    if (url === '/api/games' && method === 'POST') return json({ game_id: 'g1' });
    if (url === '/api/games/g1' && method === 'GET') return json(serverGame);
    if (url === '/api/games/g1/players') return json({ players: PLAYERS });
    if (url === '/api/games/g1/start') { serverGame = { ...serverGame, phase: 'night', day_number: 1 }; return json({ status: 'success' }); }
    if (url.startsWith('/api/games/g1/next-phase')) return json({ status: 'started' }, 202);
    if (url === '/api/games/g1' && method === 'DELETE') return json({ status: 'success' });
    return json({ detail: 'not found' }, 404);
  }));
}

const socket = () => sockets.at(-1);
const send = (event) => act(() => socket().handlers.onEvent(event));
const status = (value) => act(() => socket().handlers.onStatus(value));

async function startedGame() {
  render(<App />);
  await screen.findByText(/Local model/);
  await userEvent.click(screen.getByRole('button', { name: /Create New Game/ }));
  await screen.findByText('Ann');
  await userEvent.click(screen.getByRole('button', { name: 'Start Game' }));
  await screen.findByRole('button', { name: 'Next Phase' });
  status('open');
}

describe('App', () => {
  beforeEach(() => {
    sockets.length = 0;
    installServer();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('invites the user to create a game and shows the model', async () => {
    render(<App />);
    expect(screen.getByText(/Click "Create New Game" to begin/)).toBeInTheDocument();
    expect(await screen.findByText(/Local model/)).toBeInTheDocument();
    expect(screen.getByText('gemma3:4b')).toBeInTheDocument();
  });

  it('creates a game, shows players and hides the roles of the living', async () => {
    render(<App />);
    await screen.findByText(/Local model/);
    await userEvent.click(screen.getByRole('button', { name: /Create New Game/ }));
    expect(await screen.findByText('Ann')).toBeInTheDocument();
    expect(screen.getByText(/\[GAME MASTER\] Welcome/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start Game' })).toBeInTheDocument();
    expect(screen.getByText('🎭 Hidden')).toBeInTheDocument();
    expect(screen.getByText('🐺 Werewolf')).toBeInTheDocument();
    expect(socket().gameId).toBe('g1');
  });

  it('shows the state of the live connection', async () => {
    render(<App />);
    await screen.findByText(/Local model/);
    await userEvent.click(screen.getByRole('button', { name: /Create New Game/ }));
    await screen.findByText('Ann');
    status('connecting');
    expect(screen.getByText(/Connecting/)).toBeInTheDocument();
    status('open');
    expect(screen.getByText(/Live/)).toBeInTheDocument();
    status('reconnecting');
    expect(screen.getByText(/Reconnecting/)).toBeInTheDocument();
  });

  it('plays a phase through events instead of waiting for one long request', async () => {
    await startedGame();
    await userEvent.click(screen.getByRole('button', { name: 'Next Phase' }));

    // the request is the quick background kind and the page is waiting for events
    expect(calls).toContain('POST /api/games/g1/next-phase?background=true');
    expect(screen.getByRole('status')).toHaveTextContent('The players are thinking');
    expect(screen.getByRole('button', { name: 'Next Phase' })).toBeDisabled();

    // messages and votes show up one by one, before the phase is over
    send({ type: 'player_spoke', data: { sender: 'Ann', content: 'I trust nobody.' } });
    expect(screen.getByText('[Ann] I trust nobody.')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Ann just spoke');
    send({ type: 'vote_cast', data: { voter: 'Ann', target: 'Bob' } });
    expect(screen.getByText('[VOTE] Ann votes to eliminate Bob')).toBeInTheDocument();

    // the end of the phase reloads the real state and frees the button
    serverGame = { ...serverGame, phase: 'day', day_number: 2, game_log: ['[GAME MASTER] Day 2 begins.'] };
    send({ type: 'phase_change', data: { phase: 'day' } });
    expect(await screen.findByText('[GAME MASTER] Day 2 begins.')).toBeInTheDocument();
    expect(screen.queryByText('[Ann] I trust nobody.')).not.toBeInTheDocument(); // the server's log is the truth
    expect(screen.getByRole('button', { name: 'Next Phase' })).toBeEnabled();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.getByText('Day 2')).toBeInTheDocument();
  });

  it('announces the winner when the game ends', async () => {
    await startedGame();
    serverGame = { ...serverGame, phase: 'ended' };
    send({ type: 'phase_change', data: { phase: 'ended', game_ended: true } });
    send({ type: 'game_ended', data: { winner: 'villagers' } });
    expect(await screen.findByText(/The villagers win/)).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Next Phase' })).not.toBeInTheDocument());
  });

  it('reloads the game when the connection comes back', async () => {
    await startedGame();
    const before = calls.filter((c) => c === 'GET /api/games/g1').length;
    serverGame = { ...serverGame, game_log: ['[GAME MASTER] missed while offline'] };
    await act(async () => {
      socket().handlers.onReconnect();
    });
    expect(await screen.findByText('[GAME MASTER] missed while offline')).toBeInTheDocument();
    expect(calls.filter((c) => c === 'GET /api/games/g1').length).toBe(before + 1);
  });

  it('without a live connection it waits for the phase to finish', async () => {
    await startedGame();
    status('reconnecting');
    fetch.mockImplementation((url, options = {}) => {
      calls.push(`${options.method || 'GET'} ${url}`);
      if (url.startsWith('/api/games/g1/next-phase')) return json({ status: 'success', data: { phase: 'day' } });
      if (url === '/api/games/g1') return json({ ...serverGame, phase: 'day', day_number: 2 });
      if (url === '/api/games/g1/players') return json({ players: PLAYERS });
      return json({}, 404);
    });
    await userEvent.click(screen.getByRole('button', { name: 'Next Phase' }));
    expect(calls).toContain('POST /api/games/g1/next-phase'); // no ?background
    expect(await screen.findByText('Day 2')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Next Phase' })).toBeEnabled();
  });

  it('shows the error and frees the button when the phase cannot start', async () => {
    await startedGame();
    fetch.mockImplementation(() => json({ detail: 'This game is busy playing a phase' }, 409));
    await userEvent.click(screen.getByRole('button', { name: 'Next Phase' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('This game is busy playing a phase');
    expect(screen.getByRole('button', { name: 'Next Phase' })).toBeEnabled();
  });

  it('shows an error event from the server', async () => {
    await startedGame();
    await userEvent.click(screen.getByRole('button', { name: 'Next Phase' }));
    send({ type: 'error', data: 'Failed to progress to the next phase' });
    expect(await screen.findByRole('alert')).toHaveTextContent('Failed to progress to the next phase');
    expect(screen.getByRole('button', { name: 'Next Phase' })).toBeEnabled();
  });

  it('closes the connection of the old game and deletes it when a new game is created', async () => {
    await startedGame();
    const first = socket();
    serverGame = { ...serverGame, phase: 'setup' };
    const server = fetch.getMockImplementation();
    fetch.mockImplementation((url, options = {}) => {
      if (url === '/api/games' && options.method === 'POST') return json({ game_id: 'g2' });
      if (url === '/api/games/g2/players') return json({ players: PLAYERS });
      if (url === '/api/games/g2') return json(serverGame);
      return server(url, options);
    });
    await userEvent.click(screen.getByRole('button', { name: /Create New Game/ }));
    await waitFor(() => expect(first.closed).toBe(true));
    expect(socket().gameId).toBe('g2');
    expect(calls).toContain('DELETE /api/games/g1');
  });

  it('keeps spectator mode off and unavailable while the server hides the roles', async () => {
    await startedGame();
    const toggle = screen.getByRole('checkbox', { name: /Spectator mode/ });
    expect(toggle).not.toBeChecked();
    expect(toggle).toBeDisabled();
    expect(screen.getByText('🎭 Hidden')).toBeInTheDocument();
  });

  it('lets the user watch with all roles when the server sends them, off by default', async () => {
    const spectated = PLAYERS.map((p) => (p.id === 'p1' ? { ...p, role: 'seer' } : p));
    fetch.mockImplementation((url, options = {}) => {
      const method = options.method || 'GET';
      if (url === '/api/model') return json({ model: 'm', reachable: true, installed: true, loaded: true });
      if (url === '/api/games' && method === 'POST') return json({ game_id: 'g1' });
      if (url === '/api/games/g1') return json({ ...serverGame, players: spectated, roles_revealed: true });
      if (url === '/api/games/g1/players') return json({ players: spectated });
      return json({ detail: 'nope' }, 404);
    });
    render(<App />);
    await userEvent.click(screen.getByRole('button', { name: /Create New Game/ }));
    await screen.findByText('Ann');
    expect(screen.getByText('🎭 Hidden')).toBeInTheDocument(); // the server sent the role, the page hides it
    expect(screen.queryByText(/Seer/)).not.toBeInTheDocument();

    const toggle = screen.getByRole('checkbox', { name: /Spectator mode/ });
    expect(toggle).toBeEnabled();
    await userEvent.click(toggle);
    expect(screen.getByText(/Seer/)).toHaveClass('secret');
    await userEvent.click(toggle);
    expect(screen.queryByText(/Seer/)).not.toBeInTheDocument();
  });

  it('shows the last night and the last vote for debugging', async () => {
    await startedGame();
    serverGame = { ...serverGame, phase: 'discussion', day_number: 2, game_log: [
      '[GAME MASTER] Day 2 begins. Cy was killed.',
      '[VOTE] Ann votes to eliminate Bob',
      '[GAME MASTER] Bob has been voted out by the village. Their role was: werewolf.',
    ] };
    send({ type: 'phase_change', data: { phase: 'voting' } });
    expect(await screen.findByText('Day 2: Cy was killed.')).toBeInTheDocument();
    expect(screen.getByText(/Voted out:/)).toHaveTextContent('Voted out: Bob (werewolf)');
  });

  it('shows how much the model worked for the game once it did something', async () => {
    await startedGame();
    serverGame = { ...serverGame, llm: { calls: 12, errors: 0, invalid_answers: 0, prompt_tokens: 5000,
      completion_tokens: 500, seconds: 20, skipped_turns: 3 } };
    send({ type: 'phase_change', data: { phase: 'day' } });
    expect(await screen.findByLabelText('Model usage in this game')).toHaveTextContent('12 model calls');
  });

  it('warns clearly when Ollama is not running, and the game button still works to retry', async () => {
    fetch.mockImplementation((url) => (url === '/api/model'
      ? json({ model: 'gemma3:4b', host: 'http://localhost:11434', reachable: false, installed: false, loaded: false })
      : json({ detail: 'Ollama is not running at http://localhost:11434.' }, 503)));
    render(<App />);
    expect(await screen.findByText('Ollama is not running.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Create New Game/ }));
    expect(await screen.findByText(/Failed to create game: Ollama is not running at/)).toBeInTheDocument();
  });

  it('shows an error when the server refuses to create a game', async () => {
    fetch.mockImplementation((url) => (url === '/api/model'
      ? json({ model: 'm', reachable: true, installed: true, loaded: false })
      : json({ detail: 'Ollama is not running' }, 503)));
    render(<App />);
    await screen.findByText(/Local model/);
    await userEvent.click(screen.getByRole('button', { name: /Create New Game/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Ollama is not running');
    within(screen.getByRole('alert')).getByText(/Error/);
  });
});
