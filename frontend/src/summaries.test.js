import { describe, expect, it } from 'vitest';
import { lastNight, lastVotes } from './summaries.js';

const ROUND_1 = [
  '[GAME MASTER] The village votes.',
  '[VOTE] Ann votes to eliminate Bob',
  '[VOTE] Cy votes to eliminate Bob',
  '[VOTE] Bob votes for Ann (error fallback)',
  '[GAME MASTER] Bob has been voted out by the village. Their role was: werewolf.',
];

describe('lastVotes', () => {
  it('is null before anybody voted', () => {
    expect(lastVotes([])).toBeNull();
    expect(lastVotes(['[GAME MASTER] Welcome'])).toBeNull();
  });

  it('reads votes, with and without a reason, and tallies them', () => {
    const result = lastVotes(ROUND_1);
    expect(result.votes).toEqual([
      { voter: 'Ann', target: 'Bob' },
      { voter: 'Cy', target: 'Bob' },
      { voter: 'Bob', target: 'Ann' },
    ]);
    expect(result.tally).toEqual([
      { target: 'Bob', count: 2, voters: ['Ann', 'Cy'] },
      { target: 'Ann', count: 1, voters: ['Bob'] },
    ]);
    expect(result.eliminated).toEqual({ name: 'Bob', role: 'werewolf' });
  });

  it('only counts the latest round', () => {
    const log = [...ROUND_1, '[GAME MASTER] Night 2 falls.', '[GAME MASTER] Day 3 begins.',
      '[VOTE] Ann votes to eliminate Cy', '[VOTE] Cy votes to eliminate Ann'];
    const result = lastVotes(log);
    expect(result.votes).toHaveLength(2);
    expect(result.tally.map((t) => t.target)).toEqual(['Ann', 'Cy']); // tie: alphabetical
    expect(result.eliminated).toBeNull(); // nobody voted out yet
  });

  it('copes with names that contain spaces or digits', () => {
    const result = lastVotes(['[VOTE] Mary Ann votes to eliminate Bob2']);
    expect(result.votes).toEqual([{ voter: 'Mary Ann', target: 'Bob2' }]);
  });
});

describe('lastNight', () => {
  it('is null before the first dawn', () => {
    expect(lastNight([])).toBeNull();
    expect(lastNight(['[GAME MASTER] Night 1 falls.'])).toBeNull();
  });

  it('reads both wordings of the dawn announcement, the latest one', () => {
    const log = [
      '[GAME MASTER] Day 1 begins. Sophia was killed.',
      '[Ann] hello',
      '[GAME MASTER] The sun rises on Day 2. Cy was killed. Dee was killed. Dee was the hunter and shot Bob.',
    ];
    expect(lastNight(log)).toEqual({
      day: 2,
      text: 'Cy was killed. Dee was killed. Dee was the hunter and shot Bob.',
    });
    expect(lastNight(log.slice(0, 2))).toEqual({ day: 1, text: 'Sophia was killed.' });
  });

  it('reads the peaceful night', () => {
    expect(lastNight(['[GAME MASTER] Day 3 begins. No one was killed.'])).toEqual({ day: 3, text: 'No one was killed.' });
  });
});
