import React from 'react';

const ROLE_LABELS = {
  werewolf: '🐺 Werewolf',
  villager: '👤 Villager',
  seer: '🔮 Seer',
  witch: '🧙‍♀️ Witch',
  hunter: '🏹 Hunter',
  guard: '🛡️ Guard',
};

const TRAITS = [
  ['openness', 'Openness'],
  ['conscientiousness', 'Conscientiousness'],
  ['extraversion', 'Extraversion'],
  ['agreeableness', 'Agreeableness'],
  ['neuroticism', 'Neuroticism'],
];

/** Level of each Big Five trait, e.g. "Extraversion: very high" (one line per trait) */
export const PersonalityLevels = ({ personality }) => (
  <ul className="personality" aria-label="Personality">
    {TRAITS.map(([key, label]) => (
      <li key={key}>
        {label}: <strong>{personality?.[key] ?? '?'}</strong>
      </li>
    ))}
  </ul>
);

const LEVELS = { 'very low': 1, low: 2, medium: 3, high: 4, 'very high': 5 };

/** Gap of each flagged trait between the level found by the test and the assigned one, e.g. "extraversion +2, agreeableness -1" */
export const flaggedGaps = (check, personality) =>
  check.flagged
    .map((trait) => {
      const gap = check.measured?.[trait] - LEVELS[personality?.[trait]];
      return Number.isNaN(gap) ? trait : `${trait} ${gap > 0 ? '+' : ''}${gap}`;
    })
    .join(', ');

/**
 * One player. A role is shown only when the player is dead (everybody learns it then) or
 * when `showRole` is on (spectator mode, which needs the server to send the roles).
 */
const PlayerCard = ({ player, showRole = false, onOpenDiary }) => {
  const isDead = player.status === 'dead';
  const visible = player.role && (isDead || showRole);
  const secret = visible && !isDead; // shown only because of spectator mode

  return (
    <div className={`player-card ${isDead ? 'dead' : ''}`}>
      <h3>{player.name}</h3>
      <p>
        {player.sex} • {player.age} years
      </p>
      <PersonalityLevels personality={player.personality} />
      {player.persona_check && !player.persona_check.confirmed && (
        <p className="persona-flag" title="The psychological test found a different level than the one in the prompt">
          ⚠️ {player.persona_check.completed
            ? `Does not behave as described: ${flaggedGaps(player.persona_check, player.personality)} (score ${player.persona_check.score})`
            : 'Personality test not completed'}
        </p>
      )}
      <p
        className={secret ? 'role secret' : 'role'}
        style={{ color: '#4a90e2', fontWeight: 'bold', fontSize: '0.9em' }}
        title={secret ? 'Only visible in spectator mode' : undefined}
      >
        {visible ? ROLE_LABELS[player.role] || `🎭 ${player.role}` : '🎭 Hidden'}
        {secret && ' 👁'}
      </p>
      {onOpenDiary && (
        <button className="diary-button" onClick={() => onOpenDiary(player)}>
          📖 Diary
        </button>
      )}
      {isDead && (
        <p style={{ color: '#ff6b6b', fontWeight: 'bold' }}>
          ☠️ ELIMINATED
        </p>
      )}
    </div>
  );
};

export default PlayerCard;
