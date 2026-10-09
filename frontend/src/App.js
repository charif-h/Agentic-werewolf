import React, { useState, useEffect } from 'react';
import './App.css';
import gameApi from './services/api';
import PlayerCard from './components/PlayerCard';
import GameLog from './components/GameLog';

function App() {
  const [gameId, setGameId] = useState(null);
  const [gameState, setGameState] = useState(null);
  const [players, setPlayers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [model, setModel] = useState(null);

  // Load the local model status on mount
  useEffect(() => {
    loadModel();
  }, []);

  const loadModel = async () => {
    try {
      setModel(await gameApi.getModel());
    } catch (err) {
      console.error('Error loading model status:', err);
    }
  };

  const createGame = async () => {
    setLoading(true);
    setError(null);
    try {
      const created = await gameApi.createGame(8);
      setGameId(created.game_id);
      await loadGameState(created.game_id);
      await loadPlayers(created.game_id);
    } catch (err) {
      setError('Failed to create game: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadGameState = async (id = gameId) => {
    try {
      const data = await gameApi.getGameState(id);
      setGameState(data);
    } catch (err) {
      console.error('Error loading game state:', err);
    }
  };

  const loadPlayers = async (id = gameId) => {
    try {
      const data = await gameApi.getPlayers(id);
      setPlayers(data.players || []);
    } catch (err) {
      console.error('Error loading players:', err);
    }
  };

  const startGame = async () => {
    setLoading(true);
    setError(null);
    try {
      await gameApi.startGame(gameId);
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
      await gameApi.nextPhase(gameId);
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
        {model && (
          <p style={{ fontSize: '0.9em', color: model.installed ? '#4ecdc4' : '#ff6b6b' }}>
            {model.installed
              ? `Local model: ${model.model}`
              : model.reachable
                ? `Model ${model.model} is not installed (run: ollama pull ${model.model})`
                : 'Ollama is not running'}
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
          Create New Game (8 Players)
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
          <button onClick={() => loadGameState()} disabled={loading}>
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
