import React, { useState, useEffect } from 'react';
import './App.css';
import gameApi from './services/api';
import PlayerCard from './components/PlayerCard';
import GameLog from './components/GameLog';

function App() {
  const [gameState, setGameState] = useState(null);
  const [players, setPlayers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [providers, setProviders] = useState([]);

  // Load available providers on mount
  useEffect(() => {
    loadProviders();
  }, []);

  const loadProviders = async () => {
    try {
      const data = await gameApi.getProviders();
      setProviders(data.providers || []);
    } catch (err) {
      console.error('Error loading providers:', err);
    }
  };

  const createGame = async () => {
    setLoading(true);
    setError(null);
    try {
      await gameApi.createGame(24, null);
      await loadGameState();
      await loadPlayers();
    } catch (err) {
      setError('Failed to create game: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadGameState = async () => {
    try {
      const data = await gameApi.getGameState();
      setGameState(data);
    } catch (err) {
      console.error('Error loading game state:', err);
    }
  };

  const loadPlayers = async () => {
    try {
      const data = await gameApi.getPlayers();
      setPlayers(data.players || []);
    } catch (err) {
      console.error('Error loading players:', err);
    }
  };

  const startGame = async () => {
    setLoading(true);
    setError(null);
    try {
      await gameApi.startGame();
      await loadGameState();
    } catch (err) {
      setError('Failed to start game: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const nextPhase = async () => {
    setLoading(true);
    setError(null);
    try {
      await gameApi.nextPhase();
      await loadGameState();
      await loadPlayers();
    } catch (err) {
      setError('Failed to progress phase: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const alivePlayers = players.filter(p => p.status === 'alive');
  const deadPlayers = players.filter(p => p.status === 'dead');

  return (
    <div className="app">
      <div className="header">
        <h1>🐺 The Werewolves of Millers Hollow 🌙</h1>
        <p>AI Agents Playing the Classic Social Deduction Game</p>
        {providers.length > 0 && (
          <p style={{ fontSize: '0.9em', color: '#4ecdc4' }}>
            Available AI Providers: {providers.join(', ')}
          </p>
        )}
      </div>

      {error && (
        <div className="error">
          <strong>Error:</strong> {error}
        </div>
      )}

      <div className="controls">
        <button onClick={createGame} disabled={loading}>
          Create New Game (24 Players)
        </button>
        {gameState && gameState.phase === 'setup' && (
          <button onClick={startGame} disabled={loading}>
            Start Game
          </button>
        )}
        {gameState && gameState.phase !== 'setup' && gameState.phase !== 'ended' && (
          <button onClick={nextPhase} disabled={loading}>
            Next Phase
          </button>
        )}
        {gameState && (
          <button onClick={loadGameState} disabled={loading}>
            Refresh
          </button>
        )}
      </div>

      {loading && <div className="loading">Processing...</div>}

      {gameState && (
        <div className="game-container">
          <div className="players-panel">
            <h2>Players ({alivePlayers.length} alive)</h2>
            {alivePlayers.map(player => (
              <PlayerCard key={player.id} player={player} />
            ))}
            {deadPlayers.length > 0 && (
              <>
                <h2 style={{ marginTop: '20px', color: '#ff6b6b' }}>
                  Eliminated ({deadPlayers.length})
                </h2>
                {deadPlayers.map(player => (
                  <PlayerCard key={player.id} player={player} />
                ))}
              </>
            )}
          </div>

          <div className="game-board">
            <div className="phase-indicator">
              <h2>
                {gameState.phase === 'setup' && '⚙️ Setup'}
                {gameState.phase === 'night' && '🌙 Night'}
                {gameState.phase === 'day' && '☀️ Day'}
                {gameState.phase === 'discussion' && '💬 Discussion'}
                {gameState.phase === 'voting' && '🗳️ Voting'}
                {gameState.phase === 'ended' && '🏁 Game Ended'}
              </h2>
              <p>Day {gameState.day_number}</p>
            </div>

            <GameLog logs={gameState.game_log || []} />
          </div>
        </div>
      )}

      {!gameState && !loading && (
        <div style={{ textAlign: 'center', padding: '60px', color: '#888' }}>
          <p style={{ fontSize: '1.5em' }}>
            Click "Create New Game" to begin
          </p>
        </div>
      )}
    </div>
  );
}

export default App;
