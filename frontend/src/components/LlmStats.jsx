import React from 'react';

/** What the model did for this game: calls, speed, skipped turns (from GET /api/games/{id}) */
const LlmStats = ({ llm }) => {
  if (!llm || (llm.calls === 0 && llm.skipped_turns === 0)) return null;

  const tokens = (llm.prompt_tokens || 0) + (llm.completion_tokens || 0);
  const latency = llm.calls ? llm.seconds / llm.calls : 0;

  return (
    <div className="llm-stats" aria-label="Model usage in this game">
      <span><strong>{llm.calls}</strong> model calls</span>
      <span><strong>{Math.round(llm.seconds)}</strong> s of model time</span>
      <span><strong>{latency.toFixed(1)}</strong> s per call</span>
      <span><strong>{tokens.toLocaleString('en-US')}</strong> tokens</span>
      <span><strong>{llm.skipped_turns}</strong> turns skipped</span>
      {llm.invalid_answers > 0 && <span className="warn"><strong>{llm.invalid_answers}</strong> unusable answers</span>}
      {llm.errors > 0 && <span className="warn"><strong>{llm.errors}</strong> model errors</span>}
    </div>
  );
};

export default LlmStats;
