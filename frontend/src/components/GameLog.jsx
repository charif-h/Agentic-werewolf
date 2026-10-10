import React from 'react';

const GameLog = ({ logs }) => {
  const getLogClass = (entry) => {
    if (entry.includes('[GAME MASTER]')) return 'game-master';
    if (entry.includes('[VOTE]')) return 'system';
    return 'player';
  };

  return (
    <div className="game-log">
      <h3>Game Log</h3>
      {logs.length === 0 ? (
        <p style={{ color: '#888' }}>No events yet...</p>
      ) : (
        logs.map((entry, index) => (
          <div key={index} className={`log-entry ${getLogClass(entry)}`}>
            {entry}
          </div>
        ))
      )}
    </div>
  );
};

export default GameLog;
