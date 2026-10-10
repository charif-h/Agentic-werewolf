import { describe, expect, it } from 'vitest';
import { formatEvent, gameReducer, initialState } from './gameReducer.js';

const game = { phase: 'discussion', day_number: 2, game_log: ['[GAME MASTER] Day 2'], players: [{ id: 'a' }] };

function run(actions, start = initialState) {
  return actions.reduce(gameReducer, start);
}

describe('gameReducer', () => {
  it('starts a fresh game in setup', () => {
    const s = run([{ type: 'created', gameId: 'g1' }], { ...initialState, winner: 'villagers', log: ['x'] });
    expect(s).toMatchObject({ gameId: 'g1', phase: 'setup', winner: null, log: [] });
  });

  it('replaces the log and players with what the server says', () => {
    const s = run([{ type: 'loaded', game, players: [{ id: 'b' }] }], { ...initialState, log: ['stale'] });
    expect(s).toMatchObject({ phase: 'discussion', day: 2, log: ['[GAME MASTER] Day 2'], players: [{ id: 'b' }] });
  });

  it('shows messages and votes as they arrive', () => {
    const s = run([
      { type: 'event', event: { type: 'player_spoke', data: { sender: 'Ann', content: 'Hi' } } },
      { type: 'event', event: { type: 'vote_cast', data: { voter: 'Ann', target: 'Bob' } } },
    ]);
    expect(s.log).toEqual(['[Ann] Hi', '[VOTE] Ann votes to eliminate Bob']);
    expect(s.speaking).toBe('Ann');
  });

  it('formats live events like the server writes its log', () => {
    expect(formatEvent({ type: 'player_spoke', data: { sender: 'A', content: 'x' } })).toBe('[A] x');
    expect(formatEvent({ type: 'phase_change', data: {} })).toBeNull();
  });

  it('a phase_change ends the busy state', () => {
    const busy = run([{ type: 'busy', value: true }]);
    expect(busy.busy).toBe(true);
    const done = run([{ type: 'event', event: { type: 'phase_change', data: { phase: 'day' } } }], busy);
    expect(done).toMatchObject({ busy: false, speaking: null });
  });

  it('game_ended records the winner', () => {
    const s = run([{ type: 'event', event: { type: 'game_ended', data: { winner: 'werewolves' } } }]);
    expect(s.winner).toBe('werewolves');
  });

  it('a server error event shows the message and stops waiting', () => {
    const s = run([{ type: 'busy', value: true }, { type: 'event', event: { type: 'error', data: 'Failed' } }]);
    expect(s).toMatchObject({ busy: false, error: 'Failed' });
  });

  it('an error action stops waiting and clear_error removes the message', () => {
    const failed = run([{ type: 'busy', value: true }, { type: 'error', message: 'boom' }]);
    expect(failed).toMatchObject({ busy: false, error: 'boom' });
    expect(gameReducer(failed, { type: 'clear_error' }).error).toBeNull();
  });

  it('tracks the connection and ignores unknown events and actions', () => {
    expect(run([{ type: 'connection', status: 'reconnecting' }]).connection).toBe('reconnecting');
    const s = run([{ type: 'event', event: { type: 'echo', data: {} } }]);
    expect(s).toEqual(initialState);
    expect(gameReducer(initialState, { type: 'nope' })).toBe(initialState);
  });

  it('a reload after the end keeps the winner, a reload of a running game clears it', () => {
    const ended = { ...initialState, winner: 'villagers' };
    expect(gameReducer(ended, { type: 'loaded', game: { ...game, phase: 'ended' } }).winner).toBe('villagers');
    expect(gameReducer(ended, { type: 'loaded', game }).winner).toBeNull();
  });
});
