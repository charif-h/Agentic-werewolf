import { useCallback, useEffect, useRef, useState } from 'react';
import gameApi from '../services/api.js';

/**
 * Status of the local model, kept up to date: asked at once, then every `intervalMs`.
 *
 * Returns { status, error, checking, refresh } where status is what GET /api/model answers
 * ({ model, host, reachable, installed, loaded, size_bytes, vram_bytes }) or null before the
 * first answer, and error is set when the backend itself cannot be reached.
 */
export function useModelStatus({ intervalMs = 10000 } = {}) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const [checking, setChecking] = useState(true);
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    setChecking(true);
    try {
      const data = await gameApi.getModel();
      if (!mounted.current) return;
      setStatus(data);
      setError(null);
    } catch (err) {
      if (!mounted.current) return;
      setError(err.message);
    } finally {
      if (mounted.current) setChecking(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    refresh();
    const timer = intervalMs > 0 ? setInterval(refresh, intervalMs) : null;
    return () => {
      mounted.current = false;
      if (timer) clearInterval(timer);
    };
  }, [refresh, intervalMs]);

  return { status, error, checking, refresh };
}
