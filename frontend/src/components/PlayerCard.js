import React from 'react';

const PlayerCard = ({ player }) => {
  const isDead = player.status === 'dead';

  return (
    <div className={`player-card ${isDead ? 'dead' : ''}`}>
      <h3>{player.name}</h3>
      <p>
        {player.sex} • {player.age} years
      </p>
      <p>
        <strong>{player.personality}</strong>
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
