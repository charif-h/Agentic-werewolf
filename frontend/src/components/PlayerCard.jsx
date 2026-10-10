import React from 'react';

const ROLE_LABELS = {
  werewolf: '🐺 Werewolf',
  villager: '👤 Villager',
  seer: '🔮 Seer',
  witch: '🧙‍♀️ Witch',
  hunter: '🏹 Hunter',
  guard: '🛡️ Guard',
};

/**
 * One player. A role is shown only when the player is dead (everybody learns it then) or
 * when `showRole` is on (spectator mode, which needs the server to send the roles).
 */
const PlayerCard = ({ player, showRole = false }) => {
  const isDead = player.status === 'dead';
  const visible = player.role && (isDead || showRole);
  const secret = visible && !isDead; // shown only because of spectator mode

  return (
    <div className={`player-card ${isDead ? 'dead' : ''}`}>
      <h3>{player.name}</h3>
      <p>
        {player.sex} • {player.age} years
      </p>
      <p>
        <strong>{player.personality}</strong>
      </p>
      <p
        className={secret ? 'role secret' : 'role'}
        style={{ color: '#4a90e2', fontWeight: 'bold', fontSize: '0.9em' }}
        title={secret ? 'Only visible in spectator mode' : undefined}
      >
        {visible ? ROLE_LABELS[player.role] || `🎭 ${player.role}` : '🎭 Hidden'}
        {secret && ' 👁'}
      </p>
      <p style={{ fontSize: '0.8em', marginTop: '5px' }}>
        {player.personality_description}
      </p>
      {isDead && (
        <p style={{ color: '#ff6b6b', fontWeight: 'bold' }}>
          ☠️ ELIMINATED
        </p>
      )}
    </div>
  );
};

export default PlayerCard;
