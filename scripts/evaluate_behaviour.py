"""
Measure how the players behave, not only whether the game runs.

    python scripts/evaluate_behaviour.py --games 20 --players 8 --fake      # no model: checks the script itself
    python scripts/evaluate_behaviour.py --games 5 --players 8              # real model (Ollama)
    python scripts/evaluate_behaviour.py --games 5 --compare                # before / after milestone M7

Games are played through the same code as the server. The report (issues #72 to #82):
  * opening back-reference rate: first messages of a day that refer to an earlier talk
  * psytest pass rate: players whose five traits were all confirmed by the Big Five test
  * wolf_voted_mate: werewolf votes on a mate that were not a deliberate sacrifice (caught by the guard)
    and the deliberate sacrifices
  * diary/vote mismatch: votes that first differed from the plan written before them, and the ones
    still unexplained after asking again
  * villager vote vs diary: villagers who voted for someone other than the top suspect of their diary
    (measurable with or without plans, so it can be compared before and after the milestone)
  * reaction entries per day and model calls per day

`--compare` plays the games twice: with the behaviour features of milestone M7 off (no vote plan, no
private wolf chat, no reaction notes) and on.
"""
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from simulate import RandomPlayerClient  # noqa: E402

from backend.config import get_settings  # noqa: E402
from backend.game.game_logic import WerewolfGame  # noqa: E402
from backend.llm.factory import create_llm_client  # noqa: E402
from backend.services.phases import advance_phase  # noqa: E402

MAX_PHASES = 200
M7_FEATURES = {"VOTE_PLAN_ENABLED": "false", "WOLF_CHAT_ROUNDS": "0", "REACTIONS_PER_DAY": "0"}


def set_features(enabled: bool, environ: Optional[Dict[str, str]] = None) -> None:
    """Turn the M7 behaviour features on (the defaults) or off, through the settings"""
    import os
    environ = os.environ if environ is None else environ
    for name, off_value in M7_FEATURES.items():
        if enabled:
            environ.pop(name, None)
        else:
            environ[name] = off_value
    get_settings.cache_clear()


def run_game(num_players: int, llm) -> Dict[str, Any]:
    """Play one game to its end and return the behaviour counters"""
    game = WerewolfGame(num_players=num_players, llm=llm)
    game.setup_game()
    game.start_night()
    started = time.monotonic()

    votes = {"villager_votes": 0, "villager_off_suspect": 0}
    original_vote = game.conduct_vote

    def conduct_vote():
        result = original_vote()
        for agent in game.player_agents.values():       # before the day diary is written
            suspect = agent._top_suspect() if not agent.mates else None
            if suspect and agent.last_vote:
                votes["villager_votes"] += 1
                votes["villager_off_suspect"] += agent.last_vote != suspect
        return result

    game.conduct_vote = conduct_vote
    result: Dict[str, Any] = {}
    for _ in range(MAX_PHASES):
        result = advance_phase(game)
        if result.get("game_ended") or "error" in result:
            break
    stats = game.metrics.snapshot()
    return {
        "finished": bool(result.get("game_ended")),
        "days": max(game.state.day_number, 1),
        "seconds": time.monotonic() - started,
        "calls": stats["calls"],
        "opening_backreference": stats["opening_backreference"],
        "psytests": stats["psytests"],
        "psytest_flagged": stats["psytest_flagged"],
        "wolf_voted_mate_unintended": stats["wolf_voted_mate_unintended"],
        "wolf_sacrificed_mate": stats["wolf_sacrificed_mate"],
        "vote_plans": stats["vote_plans"],
        "diary_vote_mismatch": stats["diary_vote_mismatch"],
        "unexplained_changes": stats["unexplained_changes"],
        "reaction_entries": stats["reaction_entries"],
        "missing_reasons": stats["missing_reasons"],
        "invalid_answers": stats["invalid_answers"],
        **votes,
    }


def rate(part: float, whole: float) -> float:
    return part / whole if whole else 0.0


def summarize(games: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate the per-game counters into the rates of the report"""
    total = lambda key: sum(g[key] for g in games)       # noqa: E731
    days = total("days")
    return {
        "games": len(games),
        "days": days,
        "opening_backreference_rate": rate(total("opening_backreference"), days),
        "psytest_pass_rate": 1 - rate(total("psytest_flagged"), total("psytests")) if total("psytests") else 0.0,
        "wolf_voted_mate": total("wolf_voted_mate_unintended"),
        "wolf_sacrificed_mate": total("wolf_sacrificed_mate"),
        "vote_mismatch_rate": rate(total("diary_vote_mismatch"), total("vote_plans")),
        "unexplained_changes": total("unexplained_changes"),
        "villager_off_suspect_rate": rate(total("villager_off_suspect"), total("villager_votes")),
        "reactions_per_day": rate(total("reaction_entries"), days),
        "calls_per_day": rate(total("calls"), days),
        "missing_reasons": total("missing_reasons"),
        "invalid_answers": total("invalid_answers"),
    }


ROWS = [
    ("Opening back-reference rate", "opening_backreference_rate", "{:.1%}"),
    ("Psytest pass rate", "psytest_pass_rate", "{:.0%}"),
    ("Wolf votes on a mate (mistakes caught)", "wolf_voted_mate", "{}"),
    ("Wolf sacrifices on purpose", "wolf_sacrificed_mate", "{}"),
    ("Diary/vote mismatch rate (vote differs from the plan)", "vote_mismatch_rate", "{:.1%}"),
    ("Unexplained changes", "unexplained_changes", "{}"),
    ("Villager vote differs from the top suspect of the diary", "villager_off_suspect_rate", "{:.1%}"),
    ("Reaction entries per day", "reactions_per_day", "{:.2f}"),
    ("Model calls per day", "calls_per_day", "{:.0f}"),
    ("Decisions without a reason", "missing_reasons", "{}"),
    ("Invalid answers", "invalid_answers", "{}"),
]


def to_markdown(summaries: Dict[str, Dict[str, Any]], model: str, players: int) -> str:
    """One column per configuration (`{"M7 features on": summary, ...}`)"""
    names = list(summaries)
    header = "| Metric | " + " | ".join(names) + " |\n|---|" + "---|" * len(names) + "\n"
    body = "".join(
        f"| {label} | " + " | ".join(fmt.format(summaries[n][key]) for n in names) + " |\n"
        for label, key, fmt in ROWS)
    games = ", ".join(f"{n}: {summaries[n]['games']} games / {summaries[n]['days']} days" for n in names)
    return f"### Behaviour, {model}, {players} players\n\n{header}{body}\n{games}\n"


def play(label: str, features: bool, games: int, players: int, llm) -> Dict[str, Any]:
    set_features(features)
    results = []
    for number in range(1, games + 1):
        results.append(run_game(players, llm))
        print(f"[{label}] game {number}/{games}: {results[-1]['days']} days, {results[-1]['calls']} calls", flush=True)
    return {"games": results, "summary": summarize(results)}


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--games", type=int, default=10)
    parser.add_argument("--players", type=int, default=8)
    parser.add_argument("--model", help="Ollama model tag (default: LLM_MODEL from the settings)")
    parser.add_argument("--fake", action="store_true", help="use a random fake model instead of Ollama")
    parser.add_argument("--compare", action="store_true", help="also play with the M7 behaviour features off")
    parser.add_argument("--json", help="write the per-game results and the summaries here")
    parser.add_argument("--markdown", help="write the table here")
    args = parser.parse_args(argv)

    if args.fake:
        model, llm = "fake", RandomPlayerClient()
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

    runs = {}
    if args.compare:
        runs["M7 features off"] = play("off", False, args.games, args.players, llm)
    runs["M7 features on"] = play("on", True, args.games, args.players, llm)
    set_features(True)

    table = to_markdown({name: run["summary"] for name, run in runs.items()}, model, args.players)
    if args.json:
        Path(args.json).write_text(json.dumps({"model": model, "players": args.players, "runs": runs}, indent=1),
                                   encoding="utf-8")
    if args.markdown:
        Path(args.markdown).write_text(table, encoding="utf-8")
    print("\n" + table)
    return 0


if __name__ == "__main__":
    sys.exit(main())
