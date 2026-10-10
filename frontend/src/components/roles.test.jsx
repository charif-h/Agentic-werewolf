import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import PlayerCard from './PlayerCard.jsx';
import { NightSummary, VoteTally } from './Summaries.jsx';

const ALIVE = { id: 'p1', name: 'Ann', sex: 'female', age: 30, personality: 'INTJ', status: 'alive', role: 'seer' };
const DEAD = { ...ALIVE, id: 'p2', name: 'Bob', status: 'dead', role: 'werewolf' };

describe('PlayerCard roles', () => {
  it('hides the role of a living player by default, even if the server sent it', () => {
    render(<PlayerCard player={ALIVE} />);
    expect(screen.getByText('🎭 Hidden')).toBeInTheDocument();
    expect(screen.queryByText(/Seer/)).not.toBeInTheDocument();
  });

  it('hides it when the server sent no role at all', () => {
    render(<PlayerCard player={{ ...ALIVE, role: null }} showRole />);
    expect(screen.getByText('🎭 Hidden')).toBeInTheDocument();
  });

  it('shows the role of a dead player to everybody', () => {
    render(<PlayerCard player={DEAD} />);
    expect(screen.getByText('🐺 Werewolf')).toBeInTheDocument();
    expect(screen.getByText(/ELIMINATED/)).toBeInTheDocument();
  });

  it('shows the role of a living player in spectator mode, marked as secret', () => {
    render(<PlayerCard player={ALIVE} showRole />);
    const role = screen.getByText(/Seer/);
    expect(role).toHaveClass('secret');
    expect(role).toHaveAttribute('title', 'Only visible in spectator mode');
  });

  it('does not mark the role of a dead player as secret', () => {
    render(<PlayerCard player={DEAD} showRole />);
    expect(screen.getByText('🐺 Werewolf')).not.toHaveClass('secret');
  });

  it('falls back to the raw name for an unknown role', () => {
    render(<PlayerCard player={{ ...DEAD, role: 'jester' }} />);
    expect(screen.getByText('🎭 jester')).toBeInTheDocument();
  });
});

describe('summaries', () => {
  const log = [
    '[GAME MASTER] Day 2 begins. Cy was killed.',
    '[VOTE] Ann votes to eliminate Bob',
    '[VOTE] Dee votes to eliminate Bob',
    '[VOTE] Bob votes to eliminate Ann',
    '[GAME MASTER] Bob has been voted out by the village. Their role was: werewolf.',
  ];

  it('VoteTally lists the tally, the voters and who was voted out', () => {
    render(<VoteTally log={log} />);
    const items = screen.getAllByRole('listitem');
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent('Bob: 2 votes (Ann, Dee)');
    expect(items[1]).toHaveTextContent('Ann: 1 vote (Bob)');
    expect(screen.getByText(/Voted out:/)).toHaveTextContent('Voted out: Bob (werewolf)');
  });

  it('VoteTally says so when nobody voted', () => {
    render(<VoteTally log={[]} />);
    expect(screen.getByText('Nobody has voted yet.')).toBeInTheDocument();
  });

  it('NightSummary shows the dawn announcement', () => {
    render(<NightSummary log={log} />);
    expect(screen.getByText('Day 2: Cy was killed.')).toBeInTheDocument();
  });

  it('NightSummary says so before the first dawn', () => {
    render(<NightSummary log={['[GAME MASTER] Night 1 falls.']} />);
    expect(screen.getByText('The first night has not ended yet.')).toBeInTheDocument();
  });
});
