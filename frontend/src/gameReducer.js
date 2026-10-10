// State of the game page. Pure functions only, so the whole behaviour is easy to test.

export const initialState = {
  gameId: null,
  phase: null, // setup | night | day | discussion | voting | ended
  day: 0,
  players: [],
  log: [], // lines in the same format as the server's game log
  connection: 'closed', // connecting | open | reconnecting | closed
  busy: false, // a phase is being played by the server
  speaking: null, // name of the last player who spoke (live indicator)
  winner: null,
  llm: null, // model usage of this game (calls, tokens, time)
  error: null,
};

export function formatEvent(event) {
  const { type, data } = event;
  if (type === 'player_spoke') return `[${data.sender}] ${data.content}`;
  if (type === 'vote_cast') return `[VOTE] ${data.voter} votes to eliminate ${data.target}`;
  return null;
}

export function gameReducer(state, action) {
  switch (action.type) {
    case 'created':
      return { ...initialState, gameId: action.gameId, phase: 'setup' };

    case 'loaded': {
      // The server's answer is the truth: it replaces what the live events built up
      const { game, players } = action;
      return {
        ...state,
        phase: game.phase,
        day: game.day_number,
        players: players || game.players,
        log: game.game_log || [],
        llm: game.llm || null,
        winner: game.phase === 'ended' ? state.winner : null,
      };
    }

    case 'connection':
      return { ...state, connection: action.status };

    case 'busy':
      return { ...state, busy: action.value, speaking: action.value ? state.speaking : null };

    case 'error':
      return { ...state, error: action.message, busy: false };

    case 'clear_error':
      return { ...state, error: null };

    case 'event': {
      const { event } = action;
      const line = formatEvent(event);
      switch (event.type) {
        case 'player_spoke':
          return { ...state, log: [...state.log, line], speaking: event.data.sender };
        case 'vote_cast':
          return { ...state, log: [...state.log, line] };
        case 'phase_change':
          // Whatever the result says, the page reloads the real state right after
          return { ...state, busy: false, speaking: null };
        case 'game_ended':
          return { ...state, winner: event.data.winner, busy: false, speaking: null };
        case 'error':
          return { ...state, busy: false, speaking: null, error: String(event.data) };
        default:
          return state;
      }
    }

    default:
      return state;
  }
}
