import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App.jsx';

const PLAYERS = [
  { id: 'p1', name: 'Ann', sex: 'female', age: 30, personality: 'INTJ', status: 'alive', role: null },
  { id: 'p2', name: 'Bob', sex: 'male', age: 41, personality: 'ENFP', status: 'dead', role: 'werewolf' },
];

function json(body, status = 200) {
  return Promise.resolve({ ok: status < 400, status, statusText: '', json: () => Promise.resolve(body) });
}

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn((url, options = {}) => {
      if (url === '/api/model') return json({ model: 'gemma3:4b', reachable: true, installed: true });
      if (url === '/api/games' && options.method === 'POST') return json({ game_id: 'g1' });
      if (url === '/api/games/g1') return json({ phase: 'setup', day_number: 0, players: PLAYERS, game_log: ['[GAME MASTER] Welcome'] });
      if (url === '/api/games/g1/players') return json({ players: PLAYERS });
      return json({ detail: 'not found' }, 404);
    }));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('invites the user to create a game and shows the model', async () => {
    render(<App />);
    expect(screen.getByText(/Click "Create New Game" to begin/)).toBeInTheDocument();
    expect(await screen.findByText(/Local model: gemma3:4b/)).toBeInTheDocument();
  });

  it('creates a game and shows players and the log', async () => {
    render(<App />);
    await userEvent.click(screen.getByRole('button', { name: /Create New Game/ }));
    expect(await screen.findByText('Ann')).toBeInTheDocument();
    expect(screen.getByText(/\[GAME MASTER\] Welcome/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start Game' })).toBeInTheDocument();
    // the living player's role is hidden, the dead player's role is shown
    expect(screen.getByText('🎭 Hidden')).toBeInTheDocument();
    expect(screen.getByText('🐺 Werewolf')).toBeInTheDocument();
  });

  it('shows an error when the server refuses', async () => {
    fetch.mockImplementation((url) => (url === '/api/model'
      ? json({ model: 'm', reachable: true, installed: true })
      : json({ detail: 'Ollama is not running' }, 503)));
    render(<App />);
    await userEvent.click(screen.getByRole('button', { name: /Create New Game/ }));
    await waitFor(() => expect(screen.getByText(/Ollama is not running/)).toBeInTheDocument());
  });
});
