"""
Play complete games without a browser and report how they went.

    python scripts/simulate.py --games 20 --players 8
    python scripts/simulate.py --games 10 --model gemma3:1b --markdown results.md
    python scripts/simulate.py --games 5 --fake            # no model: checks the script itself

Games are played through the same code as the server (rules engine, agents,
prompts, JSON decisions). Use it to compare a prompt or model change: run it
before and after, with the same number of games and players, and look at the
numbers below.

Report:
  * win rate of each team and average length (days)
  * invalid-output rate: model answers that could not be used and fell back
    to a random choice (per model call)
  * average latency per model call, and time per game
  * role leaks: discussion lines in which a player stated their own role
Role assignment is random in every game, so use enough games (20 or more) before
believing a difference between two runs.
"""
import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.game.game_logic import WerewolfGame  # noqa: E402

from backend.llm.metrics import current_metrics  # noqa: E402
from backend.llm.factory import create_llm_client  # noqa: E402
from backend.services.phases import advance_phase  # noqa: E402

MAX_PHASES = 80          # a game can never need that many phases


class RandomPlayerClient:
    """A "model" that answers every question with something valid at random (for --fake)"""

    def generate(self, messages, *, max_tokens=None, temperature=None, json_schema=None) -> str:
        properties = (json_schema or {}).get("properties", {})
        if "target" in properties:
            names = properties["target"].get("enum") or ["Nobody"]
            answer = {"target": random.choice(names)}
        elif "speak" in properties:
            speak = random.random() < 0.8
            answer = {"speak": speak, "message": random.choice(["Bob looks odd.", "I trust Cy."]) if speak else ""}
        else:
            answer = {"save": False, "poison": "none"}
        metrics = current_metrics()
        if metrics is not None:
            metrics.add_call(0.0, 0.0, {})
        return json.dumps(answer)


def run_game(num_players: int, llm) -> Dict[str, Any]:
    """Play one game to its end and return what happened"""
    game = WerewolfGame(num_players=num_players, llm=llm)
    game.setup_game()
    game.start_night()
    started = time.monotonic()
    result: Dict[str, Any] = {}
    for _ in range(MAX_PHASES):
        result = advance_phase(game)
        if result.get("game_ended") or "error" in result:
            break
    stats = game.metrics.snapshot()
    return {
        "winner": result.get("winner"),
        "finished": bool(result.get("game_ended")),
        "days": game.state.day_number,
        "seconds": time.monotonic() - started,
        "calls": stats["calls"],
        "model_errors": stats["errors"],
        "invalid_answers": stats["invalid_answers"],
        "role_leaks": stats["role_leaks"],
        "skipped_turns": stats["skipped_turns"],
        "model_seconds": stats["seconds"],
        "tokens": stats["prompt_tokens"] + stats["completion_tokens"],
    }


def summarize(games: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate the per-game results"""
    finished = [g for g in games if g["finished"]]
    calls = sum(g["calls"] for g in games)
    total = max(len(games), 1)
    return {
        "games": len(games),
        "finished": len(finished),
        "villagers_win": sum(g["winner"] == "villagers" for g in finished) / max(len(finished), 1),
        "werewolves_win": sum(g["winner"] == "werewolves" for g in finished) / max(len(finished), 1),
        "avg_days": statistics.mean(g["days"] for g in games) if games else 0.0,
        "avg_game_seconds": sum(g["seconds"] for g in games) / total,
        "avg_calls_per_game": calls / total,
        "avg_latency_s": sum(g["model_seconds"] for g in games) / calls if calls else 0.0,
        "invalid_rate": sum(g["invalid_answers"] for g in games) / calls if calls else 0.0,
        "model_error_rate": sum(g["model_errors"] for g in games) / calls if calls else 0.0,
        "role_leaks": sum(g["role_leaks"] for g in games),
        "skipped_turns": sum(g["skipped_turns"] for g in games),
        "avg_tokens_per_game": sum(g["tokens"] for g in games) / total,
    }


def to_markdown(summary: Dict[str, Any], model: str, players: int) -> str:
    rows = [
        ("Games played / finished", f"{summary['games']} / {summary['finished']}"),
        ("Villagers win", f"{summary['villagers_win'] * 100:.0f}%"),
        ("Werewolves win", f"{summary['werewolves_win'] * 100:.0f}%"),
        ("Average length (days)", f"{summary['avg_days']:.1f}"),
        ("Average time per game", f"{summary['avg_game_seconds']:.0f} s"),
        ("Model calls per game", f"{summary['avg_calls_per_game']:.0f}"),
        ("Average latency per call", f"{summary['avg_latency_s']:.2f} s"),
        ("Invalid-output rate", f"{summary['invalid_rate'] * 100:.1f}%"),
        ("Model error rate", f"{summary['model_error_rate'] * 100:.1f}%"),
        ("Role leaks (own role stated)", str(summary["role_leaks"])),
        ("Discussion turns skipped", str(summary["skipped_turns"])),
        ("Tokens per game", f"{summary['avg_tokens_per_game']:.0f}"),
    ]
    table = "| Metric | Value |\n|---|---|\n" + "".join(f"| {k} | {v} |\n" for k, v in rows)
    return f"### {model}, {players} players\n\n{table}"


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")        # Windows consoles default to cp1252
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--players", type=int, default=8)
    parser.add_argument("--model", help="Ollama model tag (default: LLM_MODEL from the settings)")
    parser.add_argument("--seed", type=int, help="seed for roles and names (the model's answers still vary)")
    parser.add_argument("--fake", action="store_true", help="use a scripted fake model instead of Ollama")
    parser.add_argument("--json", help="write per-game results and the summary here")
    parser.add_argument("--markdown", help="write the summary table here")
    args = parser.parse_args(argv)

    if args.seed is not None:
        random.seed(args.seed)
    if args.fake:
        model = "fake"
        llm = RandomPlayerClient()
    else:
        llm = create_llm_client()
        if args.model:
            llm.model = args.model
        model = llm.model
        status = llm.status()
        if not (status["reachable"] and status["installed"]):
            print(f"Ollama is not ready for '{model}': reachable={status['reachable']}, "
                  f"installed={status['installed']}. Start Ollama and run: ollama pull {model}", file=sys.stderr)
            return 2
        print(f"Warm-up: {llm.warm_up():.1f} s", flush=True)

    games = []
    for number in range(1, args.games + 1):
        game = run_game(args.players, llm)
        games.append(game)
        print(f"game {number}/{args.games}: {game['winner'] or 'unfinished'} win, {game['days']} days, "
              f"{game['seconds']:.0f} s, {game['calls']} calls, {game['invalid_answers']} invalid, "
              f"{game['role_leaks']} leaks", flush=True)

    summary = summarize(games)
    table = to_markdown(summary, model, args.players)
    if args.json:
        Path(args.json).write_text(json.dumps({"model": model, "players": args.players,
                                               "summary": summary, "games": games}, indent=1), encoding="utf-8")
    if args.markdown:
        Path(args.markdown).write_text(table, encoding="utf-8")
    print("\n" + table)
    return 0 if summary["finished"] == summary["games"] else 1


if __name__ == "__main__":
    sys.exit(main())
