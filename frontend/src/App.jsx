import React from 'react';
import './App.css';
import PlayerCard from './components/PlayerCard.jsx';
import GameLog from './components/GameLog.jsx';
import LlmStats from './components/LlmStats.jsx';
import ModelStatus from './components/ModelStatus.jsx';
import { useGame } from './hooks/useGame.js';
import { useModelStatus } from './hooks/useModelStatus.js';

const PHASE_LABELS = {
  setup: '⚙️ Setup',
  night: '🌙 Night',
  day: '☀️ Day',
  discussion: '💬 Discussion',
  voting: '🗳️ Voting',
  ended: '🏁 Game Ended',
};

const CONNECTION_LABELS = {
  connecting: 'Connecting…',
  open: 'Live',
  reconnecting: 'Reconnecting…',
  closed: 'Not connected',
};

function App() {
  const { state, createGame, startGame, nextPhase, refresh } = useGame();
  const model = useModelStatus();

  const alivePlayers = state.players.filter((p) => p.status === 'alive');
  const deadPlayers = state.players.filter((p) => p.status === 'dead');
  const hasGame = state.gameId && state.phase;

  return (
    <div className="app">
      <div className="header">
        <h1>🐺 The Werewolves of Millers Hollow 🌙</h1>
        <p>AI Agents Playing the Classic Social Deduction Game</p>
        <ModelStatus model={model} />
      </div>

      {state.error && (
        <div className="error" role="alert">
          <strong>Error:</strong> {state.error}
        </div>
      )}

      <div className="controls">
        <button onClick={() => createGame(8)} disabled={state.busy}>
          Create New Game (8 Players)
        </button>
        {hasGame && state.phase === 'setup' && (
          <button onClick={startGame} disabled={state.busy}>
            Start Game
          </button>
        )}
        {hasGame && state.phase !== 'setup' && state.phase !== 'ended' && (
          <button onClick={nextPhase} disabled={state.busy}>
            Next Phase
          </button>
        )}
        {hasGame && (
          <button onClick={() => refresh()} disabled={state.busy}>
            Refresh
          </button>
        )}
        {hasGame && (
          <span className={`connection ${state.connection}`} title="Live connection to the game">
            ● {CONNECTION_LABELS[state.connection]}
          </span>
        )}
      </div>

      {state.busy && (
        <div className="loading" role="status">
          {state.speaking ? `${state.speaking} just spoke…` : 'The players are thinking…'}
        </div>
      )}

      {state.winner && (
        <div className="winner" role="status">
          🏆 The {state.winner} win!
        </div>
      )}

      {hasGame && (
        <div className="game-container">
          <div className="players-panel">
            <h2>Players ({alivePlayers.length} alive)</h2>
            {alivePlayers.map((player) => (
              <PlayerCard key={player.id} player={player} />
            ))}
            {deadPlayers.length > 0 && (
              <>
                <h2 style={{ marginTop: '20px', color: '#ff6b6b' }}>
                  Eliminated ({deadPlayers.length})
                </h2>
                {deadPlayers.map((player) => (
                  <PlayerCard key={player.id} player={player} />
                ))}
              </>
            )}
          </div>

          <div className="game-board">
            <div className="phase-indicator">
              <h2>{PHASE_LABELS[state.phase] || state.phase}</h2>
              <p>Day {state.day}</p>
            </div>

            <LlmStats llm={state.llm} />

            <GameLog logs={state.log} />
          </div>
        </div>
      )}

      {!hasGame && (
        <div style={{ textAlign: 'center', padding: '60px', color: '#888' }}>
          <p style={{ fontSize: '1.5em' }}>Click &quot;Create New Game&quot; to begin</p>
        </div>
      )}
    </div>
  );
}

export default App;
