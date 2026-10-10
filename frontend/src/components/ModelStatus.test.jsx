import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ModelStatus from './ModelStatus.jsx';
import LlmStats from './LlmStats.jsx';

const READY = {
  model: 'gemma3:4b',
  host: 'http://localhost:11434',
  reachable: true,
  installed: true,
  loaded: true,
  size_bytes: 3.35e9,
  vram_bytes: 2.88e9,
};

function show(model) {
  const refresh = vi.fn();
  render(<ModelStatus model={{ status: null, error: null, checking: false, refresh, ...model }} />);
  return refresh;
}

describe('ModelStatus', () => {
  it('says it is checking before the first answer', () => {
    show({});
    expect(screen.getByText(/Checking the local model/)).toBeInTheDocument();
  });

  it('shows the model and the memory it uses when everything is fine', () => {
    show({ status: READY });
    expect(screen.getByText('gemma3:4b')).toBeInTheDocument();
    expect(screen.getByText(/loaded in memory \(2\.9 GB\)/)).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('tells that an installed model is not loaded yet, which is not an error', () => {
    show({ status: { ...READY, loaded: false, vram_bytes: null } });
    expect(screen.getByText(/not loaded in memory yet/)).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('shows a clear banner with a retry button when Ollama is down', async () => {
    const refresh = show({ status: { ...READY, reachable: false, installed: false, loaded: false } });
    expect(screen.getByRole('alert')).toHaveTextContent('Ollama is not running');
    expect(screen.getByRole('alert')).toHaveTextContent('http://localhost:11434');
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it('tells which command installs a missing model', () => {
    show({ status: { ...READY, installed: false, loaded: false } });
    expect(screen.getByRole('alert')).toHaveTextContent('The model gemma3:4b is not installed');
    expect(screen.getByText('ollama pull gemma3:4b')).toBeInTheDocument();
  });

  it('shows a banner when the game server itself cannot be reached', () => {
    show({ error: 'Cannot reach the server' });
    expect(screen.getByRole('alert')).toHaveTextContent('The game server cannot be reached');
    expect(screen.getByRole('alert')).toHaveTextContent('Cannot reach the server');
  });

  it('keeps showing the last known status when one check fails', () => {
    show({ status: READY, error: 'Cannot reach the server' });
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByText('gemma3:4b')).toBeInTheDocument();
  });

  it('disables the retry button while a check is running', () => {
    show({ status: { ...READY, reachable: false }, checking: true });
    expect(screen.getByRole('button', { name: 'Retry' })).toBeDisabled();
  });
});

describe('LlmStats', () => {
  const stats = {
    calls: 70, errors: 0, invalid_answers: 0, prompt_tokens: 40000, completion_tokens: 3200,
    seconds: 95.4, skipped_turns: 12,
  };

  it('shows the usage of the game', () => {
    render(<LlmStats llm={stats} />);
    const box = screen.getByLabelText('Model usage in this game');
    expect(box).toHaveTextContent('70 model calls');
    expect(box).toHaveTextContent('95 s of model time');
    expect(box).toHaveTextContent('1.4 s per call');
    expect(box).toHaveTextContent('43,200 tokens');
    expect(box).toHaveTextContent('12 turns skipped');
    expect(box).not.toHaveTextContent('unusable');
  });

  it('warns about unusable answers and model errors', () => {
    render(<LlmStats llm={{ ...stats, invalid_answers: 3, errors: 1 }} />);
    expect(screen.getByLabelText('Model usage in this game')).toHaveTextContent('3 unusable answers');
    expect(screen.getByLabelText('Model usage in this game')).toHaveTextContent('1 model errors');
  });

  it('shows nothing before the model did anything', () => {
    const { container } = render(<LlmStats llm={{ ...stats, calls: 0, skipped_turns: 0 }} />);
    expect(container).toBeEmptyDOMElement();
    const missing = render(<LlmStats llm={null} />);
    expect(missing.container).toBeEmptyDOMElement();
  });
});
