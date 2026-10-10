"""scripts/simulate.py with the built-in random model (no Ollama)."""
import importlib.util
import json
import random
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "simulate.py"
spec = importlib.util.spec_from_file_location("simulate", SCRIPT)
simulate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(simulate)


def test_run_game_plays_to_the_end_and_reports_the_counters():
    random.seed(1)
    game = simulate.run_game(8, simulate.RandomPlayerClient())
    assert game["finished"] and game["winner"] in ("villagers", "werewolves")
    assert game["days"] >= 1 and game["calls"] > 10
    assert game["model_errors"] == 0 and game["invalid_answers"] == 0 and game["role_leaks"] == 0


def test_summarize():
    games = [
        {"winner": "villagers", "finished": True, "days": 2, "seconds": 10, "calls": 100, "model_errors": 0,
         "invalid_answers": 4, "role_leaks": 1, "skipped_turns": 5, "model_seconds": 30, "tokens": 1000},
        {"winner": "werewolves", "finished": True, "days": 4, "seconds": 30, "calls": 100, "model_errors": 2,
         "invalid_answers": 6, "role_leaks": 0, "skipped_turns": 7, "model_seconds": 50, "tokens": 3000},
        {"winner": None, "finished": False, "days": 9, "seconds": 20, "calls": 0, "model_errors": 0,
         "invalid_answers": 0, "role_leaks": 2, "skipped_turns": 0, "model_seconds": 0, "tokens": 0},
    ]
    s = simulate.summarize(games)
    assert (s["games"], s["finished"]) == (3, 2)
    assert s["villagers_win"] == 0.5 and s["werewolves_win"] == 0.5
    assert s["avg_days"] == 5 and s["avg_game_seconds"] == 20
    assert s["avg_latency_s"] == 0.4                     # 80 s of model time / 200 calls
    assert s["invalid_rate"] == 0.05 and s["model_error_rate"] == 0.01
    assert s["role_leaks"] == 3 and s["skipped_turns"] == 12
    assert simulate.summarize([])["games"] == 0           # no division by zero


def test_markdown_table_names_the_model_and_players():
    table = simulate.to_markdown(simulate.summarize([]), "gemma3:4b", 8)
    assert table.startswith("### gemma3:4b, 8 players")
    assert "| Invalid-output rate |" in table and "| Role leaks (own role stated) |" in table


def test_main_with_the_random_model_writes_the_reports(tmp_path, capsys):
    out_json, out_md = tmp_path / "r.json", tmp_path / "r.md"
    code = simulate.main(["--games", "3", "--players", "6", "--fake", "--seed", "5",
                          "--json", str(out_json), "--markdown", str(out_md)])
    assert code == 0
    report = json.loads(out_json.read_text(encoding="utf-8"))
    assert report["model"] == "fake" and report["players"] == 6 and len(report["games"]) == 3
    assert "Villagers win" in out_md.read_text(encoding="utf-8")
    assert "game 3/3" in capsys.readouterr().out


def test_same_seed_gives_the_same_roles_and_winners():
    def winners(seed):
        random.seed(seed)
        return [simulate.run_game(8, simulate.RandomPlayerClient())["winner"] for _ in range(4)]

    assert winners(11) == winners(11)


def test_main_refuses_to_start_without_a_ready_model(capsys):
    client = MagicMock()
    client.model = "gemma3:4b"
    client.status.return_value = {"reachable": False, "installed": False}
    with patch.object(simulate, "create_llm_client", return_value=client):
        assert simulate.main(["--games", "1"]) == 2
    assert "ollama pull gemma3:4b" in capsys.readouterr().err
    client.warm_up.assert_not_called()


def test_model_option_selects_the_model():
    client = MagicMock()
    client.model = "gemma3:4b"
    client.status.return_value = {"reachable": True, "installed": True}
    client.warm_up.return_value = 0.0
    with patch.object(simulate, "create_llm_client", return_value=client), \
            patch.object(simulate, "run_game", return_value={
                "winner": "villagers", "finished": True, "days": 1, "seconds": 0, "calls": 1, "model_errors": 0,
                "invalid_answers": 0, "role_leaks": 0, "skipped_turns": 0, "model_seconds": 0, "tokens": 0}):
        assert simulate.main(["--games", "1", "--model", "gemma3:1b"]) == 0
    assert client.model == "gemma3:1b"


def test_agent_counts_invalid_answers_and_role_leaks_in_the_tracked_game():
    from backend.agents.player_agent import PlayerAgent
    from backend.llm import FakeLLMClient
    from backend.llm.metrics import LLMMetrics, track
    from backend.models.game_models import PersonalityType, PlayerProfile, Role, Sex

    profile = PlayerProfile(id="p", name="Ann", sex=Sex.FEMALE, age=30,
                            personality=PersonalityType.INTJ, role=Role.SEER)
    metrics = LLMMetrics()
    with track(metrics):
        PlayerAgent(profile, FakeLLMClient("nonsense", wrap_json=False)).vote("", ["Ann", "Bob"])
        PlayerAgent(profile, FakeLLMClient("I am the seer, trust me.")).discuss("[Bob] hi", ["Ann", "Bob"])
    snapshot = metrics.snapshot()
    assert snapshot["invalid_answers"] == 1
    assert snapshot["role_leaks"] == 2                   # leaked, was asked again, leaked again
