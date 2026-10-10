import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createGameSocket, socketUrl } from './socket.js';

class FakeWebSocket {
  static instances = [];

  constructor(url) {
    this.url = url;
    this.closed = false;
    FakeWebSocket.instances.push(this);
  }

  close() {
    this.closed = true;
  }

  open() {
    this.onopen();
  }

  receive(data) {
    this.onmessage({ data: typeof data === 'string' ? data : JSON.stringify(data) });
  }

  drop(code = 1006) {
    this.onclose({ code });
  }
}

function setup(extra = {}) {
  const events = [];
  const statuses = [];
  const onReconnect = vi.fn();
  const handle = createGameSocket('g1', {
    WebSocketImpl: FakeWebSocket,
    url: 'ws://test/ws/g1',
    onEvent: (e) => events.push(e),
    onStatus: (s) => statuses.push(s),
    onReconnect,
    ...extra,
  });
  return { handle, events, statuses, onReconnect, current: () => FakeWebSocket.instances.at(-1) };
}

describe('socketUrl', () => {
  it('is relative to the page by default', () => {
    expect(socketUrl('g1', '', { protocol: 'http:', host: 'localhost:3000' })).toBe('ws://localhost:3000/ws/g1');
    expect(socketUrl('g1', '', { protocol: 'https:', host: 'game.example' })).toBe('wss://game.example/ws/g1');
  });

  it('follows an explicit API address', () => {
    expect(socketUrl('g1', 'http://gpu-box:8000')).toBe('ws://gpu-box:8000/ws/g1');
    expect(socketUrl('g1', 'https://api.example')).toBe('wss://api.example/ws/g1');
  });
});

describe('createGameSocket', () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('connects, reports the status and passes events on', () => {
    const { events, statuses, current } = setup();
    expect(current().url).toBe('ws://test/ws/g1');
    expect(statuses).toEqual(['connecting']);
    current().open();
    current().receive({ type: 'player_spoke', data: { sender: 'Ann', content: 'Hi' } });
    expect(statuses).toEqual(['connecting', 'open']);
    expect(events).toEqual([{ type: 'player_spoke', data: { sender: 'Ann', content: 'Hi' } }]);
  });

  it('ignores messages that are not JSON events', () => {
    const { events, current } = setup();
    current().open();
    current().receive('not json');
    current().receive({ no: 'type' });
    current().receive('[1,2]');
    expect(events).toEqual([]);
  });

  it('reconnects with a growing delay and asks for a reload when it is back', () => {
    const { statuses, onReconnect, current } = setup({ baseDelay: 100, maxDelay: 350 });
    current().open();
    expect(onReconnect).not.toHaveBeenCalled(); // the first connection is not a reconnection

    current().drop();
    expect(statuses.at(-1)).toBe('reconnecting');
    expect(FakeWebSocket.instances).toHaveLength(1);
    vi.advanceTimersByTime(99);
    expect(FakeWebSocket.instances).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(FakeWebSocket.instances).toHaveLength(2);

    current().drop(); // fails again: 200 ms
    vi.advanceTimersByTime(199);
    expect(FakeWebSocket.instances).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(FakeWebSocket.instances).toHaveLength(3);

    current().drop(); // 400 ms, but capped at 350
    vi.advanceTimersByTime(350);
    expect(FakeWebSocket.instances).toHaveLength(4);

    current().open();
    expect(statuses.at(-1)).toBe('open');
    expect(onReconnect).toHaveBeenCalledTimes(1);

    current().drop(); // the delay starts from the beginning again
    vi.advanceTimersByTime(100);
    expect(FakeWebSocket.instances).toHaveLength(5);
  });

  it('gives up when the game does not exist', () => {
    const { statuses, current } = setup();
    current().drop(4404);
    vi.advanceTimersByTime(60000);
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(statuses.at(-1)).toBe('closed');
  });

  it('close() stops everything, including a pending retry', () => {
    const { handle, statuses, current } = setup();
    current().open();
    current().drop();
    handle.close();
    vi.advanceTimersByTime(60000);
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(statuses.at(-1)).toBe('closed');

    const second = setup();
    second.current().open();
    second.handle.close();
    expect(second.current().closed).toBe(true);
    second.current().drop(); // a late close event after we closed does not reconnect
    vi.advanceTimersByTime(60000);
    expect(FakeWebSocket.instances).toHaveLength(2);
  });
});
