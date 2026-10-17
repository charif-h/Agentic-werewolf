import React, { useEffect, useState } from 'react';
import gameApi from '../services/api.js';

const GUESS_LABELS = {
  werewolf: '🐺 werewolf',
  villager: '👤 villager',
  unsure: '❔ unsure',
};

const PLAN_LABELS = {
  frame: '🎯 frame',
  ignore: '🙈 ignore',
  ally: '🤝 ally',
};

// icon and label of each kind of entry; the class `kind-<kind>` gives it its colour
export const KINDS = {
  role_card: { icon: '🃏', label: 'Role card' },
  pack: { icon: '🐺', label: 'Pack' },
  reaction: { icon: '💭', label: 'Reaction' },
  decision: { icon: '⚖️', label: 'Decision' },
  plan: { icon: '🧭', label: 'Plan' },
  night_summary: { icon: '🌙', label: 'Night' },
  day_summary: { icon: '☀️', label: 'Day' },
};

// A tag on a decision or a plan says why it is special; the sacrifice must not look like a bug
const TAGS = {
  intentional_sacrifice: { label: '🎭 Intentional sacrifice of a mate', className: 'sacrifice' },
  plan_change: { label: '↪ Changed the plan, and said why', className: 'change' },
  plan_restored: { label: '↩ Back to the plan', className: 'change' },
};

const kindOf = (entry) => KINDS[entry.kind] || { icon: entry.step.startsWith('Night') ? '🌙' : '☀️', label: '' };

/** The diary entries to show: those of the server, then the live ones it does not know yet */
export function mergeEntries(loaded, live = []) {
  const ids = new Set(loaded.map((e) => e.id).filter((id) => id !== undefined));
  return [...loaded, ...live.filter((e) => !ids.has(e.id))];
}

/**
 * The private diary of one player, newest entry first: the role card and the pack, the reasons of
 * every decision (a vote also says why not the runner-up), plans, reactions, and the summary of each
 * night and day with an opinion on each other player. It is loaded when it opens and again when the
 * game moves on (`version` changes); entries sent live (`liveEntries`) are added at once.
 */
const DiaryModal = ({ gameId, player, version, liveEntries = [], onClose }) => {
  const [entries, setEntries] = useState(null); // null: loading
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    gameApi
      .getDiary(gameId, player.id)
      .then((data) => {
        if (!cancelled) {
          setEntries(data.entries);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, player.id, version]);

  const shown = entries ? mergeEntries(entries, liveEntries) : null;

  return (
    <div className="diary-backdrop" onClick={onClose}>
      <div
        className="diary-modal"
        role="dialog"
        aria-label={`Diary of ${player.name}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="diary-header">
          <h2>📖 Diary of {player.name}</h2>
          <button onClick={onClose} aria-label="Close diary">✕</button>
        </div>
        <p className="diary-subtitle">
          {player.age} years • {Object.entries(player.personality || {}).map(([t, l]) => `${t} ${l}`).join(' · ')}
        </p>

        {error && <p className="error" role="alert">{error}</p>}
        {!error && shown === null && <p>Loading…</p>}
        {!error && shown && shown.length === 0 && (
          <p>{player.name} has not written anything yet. The first entry is the role card.</p>
        )}
        {!error && shown && [...shown].reverse().map((entry) => {
          const kind = kindOf(entry);
          const tag = TAGS[entry.data?.tag];
          const notChosen = entry.data?.not_chosen;
          // the "why not" line of a vote is shown on its own line
          const text = notChosen ? (entry.text ?? entry.summary).split(' Why not ')[0] : entry.text ?? entry.summary;
          return (
            <section
              key={entry.id ?? entry.step}
              className={`diary-entry kind-${entry.kind || 'summary'}${tag ? ` ${tag.className}` : ''}`}
            >
              <h3>{kind.icon} {entry.step}</h3>
              {tag && <p className={`diary-tag ${tag.className}`}>{tag.label}</p>}
              <p className="diary-summary">{text}</p>
              {notChosen && (
                <p className="diary-whynot">Why not {notChosen.player}: {notChosen.why_not}</p>
              )}
              <ul>
                {(entry.opinions || []).map((opinion) => (
                  <li key={opinion.player}>
                    <strong>{opinion.player}</strong>{' '}
                    {opinion.plan ? (
                      <span className={`plan ${opinion.plan}`}>({PLAN_LABELS[opinion.plan] || opinion.plan})</span>
                    ) : (
                      <span className={`guess ${opinion.guess}`}>
                        ({GUESS_LABELS[opinion.guess] || opinion.guess}, {opinion.confidence})
                      </span>
                    )}
                    : {opinion.reason}
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
      </div>
    </div>
  );
};

export default DiaryModal;
