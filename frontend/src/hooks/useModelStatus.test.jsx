import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useModelStatus } from './useModelStatus.js';

const READY = { model: 'gemma3:4b', reachable: true, installed: true, loaded: true };

function answer(body, status = 200) {
  return Promise.resolve({ ok: status < 400, status, statusText: '', json: () => Promise.resolve(body) });
}

describe('useModelStatus', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('fetch', vi.fn(() => answer(READY)));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('asks at once and then at every interval', async () => {
    const { result } = renderHook(() => useModelStatus({ intervalMs: 5000 }));
    expect(result.current.status).toBeNull();
    expect(result.current.checking).toBe(true);
    await act(async () => {});
    expect(result.current.status).toEqual(READY);
    expect(result.current.checking).toBe(false);
    expect(fetch).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(5000);
    });
    expect(fetch).toHaveBeenCalledTimes(2);
    await act(async () => {
      vi.advanceTimersByTime(10000);
    });
    expect(fetch).toHaveBeenCalledTimes(4);
  });

  it('notices when Ollama goes down and when it comes back', async () => {
    const { result } = renderHook(() => useModelStatus({ intervalMs: 5000 }));
    await act(async () => {});
    fetch.mockImplementation(() => answer({ ...READY, reachable: false, installed: false, loaded: false }));
    await act(async () => {
      vi.advanceTimersByTime(5000);
    });
    expect(result.current.status.reachable).toBe(false);
    fetch.mockImplementation(() => answer(READY));
    await act(async () => {
      vi.advanceTimersByTime(5000);
    });
    expect(result.current.status.reachable).toBe(true);
  });

  it('reports a backend that cannot be reached, and recovers', async () => {
    fetch.mockImplementation(() => Promise.reject(new TypeError('Failed to fetch')));
    const { result } = renderHook(() => useModelStatus({ intervalMs: 5000 }));
    await act(async () => {});
    expect(result.current.error).toBe('Cannot reach the server');
    expect(result.current.status).toBeNull();
    fetch.mockImplementation(() => answer(READY));
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.error).toBeNull();
    expect(result.current.status).toEqual(READY);
  });

  it('stops asking when the page goes away, and can be switched off', async () => {
    const { unmount } = renderHook(() => useModelStatus({ intervalMs: 5000 }));
    await act(async () => {});
    unmount();
    await act(async () => {
      vi.advanceTimersByTime(60000);
    });
    expect(fetch).toHaveBeenCalledTimes(1);

    fetch.mockClear();
    renderHook(() => useModelStatus({ intervalMs: 0 }));
    await act(async () => {
      vi.advanceTimersByTime(60000);
    });
    expect(fetch).toHaveBeenCalledTimes(1); // only the first check
  });
});
