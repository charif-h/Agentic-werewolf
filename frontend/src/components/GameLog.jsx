import React, { useEffect, useRef } from 'react';

const GameLog = ({ logs }) => {
  const endRef = useRef(null);

  // Keep the newest line in view while messages arrive
  useEffect(() => {
    if (endRef.current && endRef.current.scrollIntoView) {
      endRef.current.scrollIntoView({ block: 'nearest' });
    }
  }, [logs.length]);

  const getLogClass = (entry) => {
    if (entry.includes('[GAME MASTER]')) return 'game-master';
    if (entry.includes('[VOTE]')) return 'system';
    return 'player';
  };

  return (
    <div className="game-log" aria-live="polite">
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
      <div ref={endRef} />
    </div>
  );
};

export default GameLog;
