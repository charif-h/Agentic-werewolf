import { useCallback, useEffect, useReducer, useRef } from 'react';
import gameApi from '../services/api.js';
import { createGameSocket } from '../services/socket.js';
import { gameReducer, initialState } from '../gameReducer.js';

/**
 * Everything the game page needs: the state, and the actions create / start / play the next
 * phase. Progress arrives as WebSocket events (messages and votes show up as they happen);
 * the REST calls only start things and reload the state when a phase is over.
 */
export function useGame({ createSocket = createGameSocket } = {}) {
  const [state, dispatch] = useReducer(gameReducer, initialState);
  const gameIdRef = useRef(null);
  const connectionRef = useRef('closed');
  gameIdRef.current = state.gameId;
  connectionRef.current = state.connection;

  const fail = useCallback((prefix, err) => {
    dispatch({ type: 'error', message: `${prefix}: ${err.message}` });
  }, []);

  const refresh = useCallback(async (id = gameIdRef.current) => {
    if (!id) return;
    try {
      const [game, players] = await Promise.all([gameApi.getGameState(id), gameApi.getPlayers(id)]);
      dispatch({ type: 'loaded', game, players: players.players });
    } catch (err) {
      fail('Could not load the game', err);
    }
  }, [fail]);

  // Follow the live events of the current game
  useEffect(() => {
    if (!state.gameId) return undefined;
    const socket = createSocket(state.gameId, {
      onEvent: (event) => {
        dispatch({ type: 'event', event });
        if (event.type === 'phase_change') refresh();
      },
      onStatus: (status) => dispatch({ type: 'connection', status }),
      onReconnect: () => {
        refresh();
      },
    });
    return () => socket.close();
  }, [state.gameId, createSocket, refresh]);

  const createGame = useCallback(async (numPlayers = 8) => {
    dispatch({ type: 'clear_error' });
    const previous = gameIdRef.current;
    try {
      const created = await gameApi.createGame(numPlayers);
      dispatch({ type: 'created', gameId: created.game_id });
      await refresh(created.game_id);
      if (previous) gameApi.deleteGame(previous).catch(() => {}); // free the old game on the server
    } catch (err) {
      fail('Failed to create game', err);
    }
  }, [refresh, fail]);

  const startGame = useCallback(async () => {
    dispatch({ type: 'clear_error' });
    try {
      await gameApi.startGame(gameIdRef.current);
      await refresh();
    } catch (err) {
      fail('Failed to start game', err);
    }
  }, [refresh, fail]);

  const nextPhase = useCallback(async () => {
    dispatch({ type: 'clear_error' });
    dispatch({ type: 'busy', value: true });
    try {
      if (connectionRef.current === 'open') {
        // The server answers at once; messages, votes and the end of the phase come as events
        await gameApi.nextPhase(gameIdRef.current, { background: true });
      } else {
        // No live connection: wait for the result instead, then reload
        await gameApi.nextPhase(gameIdRef.current);
        dispatch({ type: 'busy', value: false });
        await refresh();
      }
    } catch (err) {
      dispatch({ type: 'busy', value: false });
      fail('Failed to progress phase', err);
    }
  }, [refresh, fail]);

  return { state, createGame, startGame, nextPhase, refresh };
}
