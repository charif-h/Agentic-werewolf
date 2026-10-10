import { API_BASE_URL } from './api.js';

/**
 * Address of a game's WebSocket. Relative to the page by default (the dev server and
 * nginx forward /ws to the backend); follows VITE_API_URL when that is set.
 */
export function socketUrl(gameId, base = API_BASE_URL, loc = window.location) {
  if (base) {
    return `${base.replace(/^http/, 'ws')}/ws/${gameId}`;
  }
  const scheme = loc.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${scheme}//${loc.host}/ws/${gameId}`;
}

/**
 * Follow the live events of one game and keep the connection alive.
 *
 * Calls onEvent({ type, data }) for every message, onStatus('connecting' | 'open' |
 * 'reconnecting' | 'closed') when the state of the connection changes, and
 * onReconnect() after a connection that came back (events may have been missed).
 * A lost connection is retried with exponential backoff; an unknown game (close
 * code 4404) is not retried.
 *
 * Returns { close }.
 */
export function createGameSocket(gameId, options) {
  const {
    onEvent,
    onStatus = () => {},
    onReconnect = () => {},
    WebSocketImpl = WebSocket,
    baseDelay = 500,
    maxDelay = 8000,
    url = socketUrl(gameId),
  } = options;

  let socket = null;
  let timer = null;
  let attempts = 0;
  let closedByUs = false;
  let wasConnected = false;

  function connect() {
    onStatus(attempts === 0 ? 'connecting' : 'reconnecting');
    socket = new WebSocketImpl(url);

    socket.onopen = () => {
      const comingBack = wasConnected || attempts > 0;
      attempts = 0;
      wasConnected = true;
      onStatus('open');
      if (comingBack) onReconnect();
    };

    socket.onmessage = (message) => {
      let event;
      try {
        event = JSON.parse(message.data);
      } catch (err) {
        return; // not for us
      }
      if (event && typeof event.type === 'string') onEvent(event);
    };

    socket.onerror = () => {
      // onclose follows and schedules the retry
    };

    socket.onclose = (closeEvent) => {
      if (closedByUs) return;
      if (closeEvent && closeEvent.code === 4404) {
        onStatus('closed'); // the game does not exist (any more)
        return;
      }
      attempts += 1;
      onStatus('reconnecting');
      timer = setTimeout(connect, Math.min(maxDelay, baseDelay * 2 ** (attempts - 1)));
    };
  }

  connect();

  return {
    close() {
      closedByUs = true;
      clearTimeout(timer);
      if (socket) socket.close();
      onStatus('closed');
    },
  };
}
