import React, { useEffect, useState } from 'react';
import gameApi from '../services/api.js';

const GUESS_LABELS = {
  werewolf: '🐺 werewolf',
  villager: '👤 villager',
  unsure: '❔ unsure',
};

const KIND_ICONS = {
  role_card: '🃏',
  pack: '🐺',
  reaction: '💭',
  decision: '⚖️',
  plan: '🧭',
  night_summary: '🌙',
  day_summary: '☀️',
};

/**
 * The private diary of one player: the role card first, then one entry per night and day, with an
 * opinion on each other player and the reason for it. It is loaded when it opens and again when the game moves on
 * (`version` changes), so a diary left open follows the game.
 */
const DiaryModal = ({ gameId, player, version, onClose }) => {
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
        {!error && entries === null && <p>Loading…</p>}
        {!error && entries && entries.length === 0 && (
          <p>{player.name} has not written anything yet. The first entry comes at dawn.</p>
        )}
        {!error && entries && [...entries].reverse().map((entry) => (
          <section key={entry.id ?? entry.step} className="diary-entry">
            <h3>
              {KIND_ICONS[entry.kind] || (entry.step.startsWith('Night') ? '🌙' : '☀️')} {entry.step}
            </h3>
            <p className="diary-summary">{entry.text ?? entry.summary}</p>
            <ul>
              {(entry.opinions || []).map((opinion) => (
                <li key={opinion.player}>
                  <strong>{opinion.player}</strong>{' '}
                  <span className={`guess ${opinion.guess}`}>
                    ({GUESS_LABELS[opinion.guess] || opinion.guess}, {opinion.confidence})
                  </span>
                  : {opinion.reason}
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
};

export default DiaryModal;
