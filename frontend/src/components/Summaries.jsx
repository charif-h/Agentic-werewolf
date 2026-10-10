import React from 'react';
import { lastNight, lastVotes } from '../summaries.js';

/** Who voted for whom in the latest round, as a tally (debugging view) */
export const VoteTally = ({ log }) => {
  const result = lastVotes(log);
  return (
    <details className="summary" open>
      <summary>Last vote</summary>
      {!result ? (
        <p className="muted">Nobody has voted yet.</p>
      ) : (
        <>
          <ul className="tally">
            {result.tally.map(({ target, count, voters }) => (
              <li key={target}>
                <strong>{target}</strong>: {count} {count === 1 ? 'vote' : 'votes'}
                <span className="muted"> ({voters.join(', ')})</span>
              </li>
            ))}
          </ul>
          {result.eliminated && (
            <p>
              Voted out: <strong>{result.eliminated.name}</strong> ({result.eliminated.role})
            </p>
          )}
        </>
      )}
    </details>
  );
};

/** What happened during the last night, as announced at dawn (debugging view) */
export const NightSummary = ({ log }) => {
  const night = lastNight(log);
  return (
    <details className="summary" open>
      <summary>Last night</summary>
      {!night ? <p className="muted">The first night has not ended yet.</p> : <p>Day {night.day}: {night.text}</p>}
    </details>
  );
};
