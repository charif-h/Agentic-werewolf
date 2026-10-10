// What happened, read back from the game log. Working from the log (instead of from events)
// means the same views work live and after the page is reloaded.

const VOTE = /^\[VOTE\] (.+?) votes (?:to eliminate|for) (.+?)(?: \(.*\))?$/;
const DAWN = /^\[GAME MASTER\] (?:Day (\d+) begins|The sun rises on Day (\d+))\. (.*)$/;
const ELIMINATION = /^\[GAME MASTER\] (.+?) has been voted out by the village\. Their role was: (.+?)\.$/;

/**
 * The votes of the latest voting round: the last unbroken run of [VOTE] lines.
 * Returns { votes: [{ voter, target }], tally: [{ target, count, voters }] } with the tally
 * sorted from most to fewest votes (ties alphabetically), or null when nobody voted yet.
 */
export function lastVotes(log) {
  let end = log.length - 1;
  while (end >= 0 && !VOTE.test(log[end])) end -= 1;
  if (end < 0) return null;
  let start = end;
  while (start > 0 && VOTE.test(log[start - 1])) start -= 1;

  const votes = log.slice(start, end + 1).map((line) => {
    const [, voter, target] = VOTE.exec(line);
    return { voter, target };
  });

  const byTarget = new Map();
  votes.forEach(({ voter, target }) => {
    const entry = byTarget.get(target) || { target, count: 0, voters: [] };
    entry.count += 1;
    entry.voters.push(voter);
    byTarget.set(target, entry);
  });
  const tally = [...byTarget.values()].sort((a, b) => b.count - a.count || a.target.localeCompare(b.target));

  // Who was voted out right after this round, if the log says so
  const next = log.slice(end + 1).map((line) => ELIMINATION.exec(line)).find(Boolean);
  return { votes, tally, eliminated: next ? { name: next[1], role: next[2] } : null };
}

/** The latest dawn announcement: { day, text } ("Cy was killed."), or null before the first dawn. */
export function lastNight(log) {
  for (let i = log.length - 1; i >= 0; i -= 1) {
    const match = DAWN.exec(log[i]);
    if (match) return { day: Number(match[1] || match[2]), text: match[3] };
  }
  return null;
}
