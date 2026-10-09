import React from 'react';

const PlayerCard = ({ player }) => {
  const isDead = player.status === 'dead';

  const getRoleDisplay = (role) => {
    if (!role) return '🎭 Hidden';
    
    const roleDisplayMap = {
      'werewolf': '🐺 Werewolf',
      'villager': '👤 Villager',
      'seer': '🔮 Seer',
      'witch': '🧙‍♀️ Witch',
      'hunter': '🏹 Hunter',
      'guard': '🛡️ Guard',
    };
    
    return roleDisplayMap[role] || `🎭 ${role}`;
  };

  // Debug log to check if role is present
  console.log(`PlayerCard for ${player.name}: role = ${player.role}`);

  return (
    <div className={`player-card ${isDead ? 'dead' : ''}`}>
      <h3>{player.name}</h3>
      <p>
        {player.sex} • {player.age} years
      </p>
      <p>
        <strong>{player.personality}</strong>
      </p>
      <p style={{ color: '#4a90e2', fontWeight: 'bold', fontSize: '0.9em' }}>
        {getRoleDisplay(player.role)}
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
