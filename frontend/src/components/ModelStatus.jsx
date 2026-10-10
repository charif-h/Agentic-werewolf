import React from 'react';

const GB = 1e9;

function gigabytes(bytes) {
  return bytes ? ` (${(bytes / GB).toFixed(1)} GB)` : '';
}

/**
 * The state of the local model, as a short line, and a banner with what to do when something
 * is wrong. `model` is { status, error, checking, refresh } from useModelStatus.
 */
const ModelStatus = ({ model }) => {
  const { status, error, checking, refresh } = model;

  if (error && !status) {
    return (
      <div className="model-banner problem" role="alert">
        <strong>The game server cannot be reached.</strong> {error}. Is the backend running?
        <button onClick={refresh} disabled={checking}>Retry</button>
      </div>
    );
  }

  if (!status) {
    return <p className="model-line checking">Checking the local model…</p>;
  }

  if (!status.reachable) {
    return (
      <div className="model-banner problem" role="alert">
        <strong>Ollama is not running.</strong> The players need it to think. Start Ollama
        (it listens on {status.host}), then retry.
        <button onClick={refresh} disabled={checking}>Retry</button>
      </div>
    );
  }

  if (!status.installed) {
    return (
      <div className="model-banner problem" role="alert">
        <strong>The model {status.model} is not installed.</strong> Run{' '}
        <code>ollama pull {status.model}</code>, then retry.
        <button onClick={refresh} disabled={checking}>Retry</button>
      </div>
    );
  }

  if (!status.loaded) {
    return (
      <p className="model-line idle" title={`Installed${gigabytes(status.size_bytes)}`}>
        Local model: <strong>{status.model}</strong> · installed, not loaded in memory yet
        (the first answer takes longer)
      </p>
    );
  }

  return (
    <p className="model-line ready">
      Local model: <strong>{status.model}</strong> · loaded in memory{gigabytes(status.vram_bytes)}
    </p>
  );
};

export default ModelStatus;
