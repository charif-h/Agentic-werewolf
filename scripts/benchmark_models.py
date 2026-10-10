"""
Benchmark local models on the prompts the game really sends.

    python scripts/benchmark_models.py gemma3:1b gemma3:4b --repeats 2 --markdown docs/model-benchmark-results.md

For every model it plays a fixed set of scenarios through the real PlayerAgent
(discussion, vote, night target, witch decision) and reports:
  * validity: how often the answer names a valid player (exactly, or after parsing)
  * discussion quality: role leaks, "no comment", length, diversity
  * speed and memory: tokens/s, seconds per answer, model load time, VRAM
Nothing here needs the game server, only a running Ollama with the models pulled.
"""
import argparse
import json
import random
import re
import statistics
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.agents.player_agent import PlayerAgent  # noqa: E402
from backend.config import get_settings  # noqa: E402
from backend.game.targets import match_player_name, parse_witch_answer  # noqa: E402
from backend.llm import Message  # noqa: E402
from backend.llm.ollama_client import OllamaClient  # noqa: E402
from backend.models.game_models import PersonalityType, PlayerProfile, Role, Sex  # noqa: E402
from backend.prompts import leaks_own_role  # noqa: E402

NAMES = ["Ann", "Bob", "Cy", "Dee", "Eli", "Fay", "Gus", "Hal"]
PERSONALITIES = [PersonalityType.INTJ, PersonalityType.ENFP, PersonalityType.ISFJ,
                 PersonalityType.ESTP, PersonalityType.INFP, PersonalityType.ENTJ]
ROLE_WORDS = re.compile(r"\b(werewolf|werewolves|villager|villagers|seer|witch|hunter|guard)\b", re.I)

CONVERSATIONS = [
    "",
    "[Bob] I slept badly. Does anyone know what happened to Hal?\n[Cy] Hal was killed. We should find who did it.",
    "[Dee] Eli has been very quiet since the start.\n[Eli] I am just listening. Why do you look at me, Dee?\n"
    "[Fay] Dee accuses very fast, that is strange too.\n[Gus] Let us not fight, we need facts.",
    "[Cy] I think Ann is hiding something.\n[Ann] That is unfair, I was only asking questions.\n"
    "[Bob] Ann did ask many questions yesterday.\n[Dee] Cy changed his story twice.\n[Cy] No I did not!",
]
ROLES = [Role.WEREWOLF, Role.VILLAGER, Role.SEER, Role.WITCH, Role.HUNTER, Role.GUARD]


def make_agent(client, index: int, role: Role) -> PlayerAgent:
    profile = PlayerProfile(id="p0", name="Ann", sex=Sex.FEMALE, age=25 + index,
                            personality=PERSONALITIES[index % len(PERSONALITIES)], role=role)
    return PlayerAgent(profile, client)


def game_state(candidates: List[str]) -> Dict[str, Any]:
    return {"phase": "night", "day_number": 2, "players": [{"name": n, "status": "alive"} for n in NAMES],
            "recent_events": [], "discussion_history": [], "valid_targets": candidates}


class Recorder:
    """Wraps a client and keeps every raw answer with the time it took"""

    def __init__(self, client: OllamaClient):
        self.client = client
        self.records: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def generate(self, messages, **options):
        started = time.monotonic()
        text = self.client.generate(messages, **options)
        with self._lock:
            self.records.append({"seconds": time.monotonic() - started, "text": text})
        return text


def clean(text: str) -> str:
    return text.strip().strip("\"'`.,;:!?*()[]{} \n\t")


def run_scenarios(client: OllamaClient, repeats: int, seed: int) -> Dict[str, List[Dict[str, Any]]]:
    rng = random.Random(seed)
    recorder = Recorder(client)
    results: Dict[str, List[Dict[str, Any]]] = {"discussion": [], "vote": [], "night": [], "witch": []}

    def last(kind: str, **extra):
        results[kind].append({**recorder.records[-1], **extra})

    for repeat in range(repeats):
        for index, conversation in enumerate(CONVERSATIONS):
            for role in ROLES:
                agent = make_agent(recorder, index + repeat, role)
                agent.discuss(conversation, NAMES)
                last("discussion", role=role.value)

                others = [n for n in NAMES if n != "Ann"]
                agent = make_agent(recorder, index + repeat, role)
                agent.vote(conversation, NAMES)
                last("vote", candidates=others)

        for role in (Role.WEREWOLF, Role.SEER, Role.GUARD):
            for index in range(4):
                targets = rng.sample(NAMES[1:], 4) if role != Role.GUARD else NAMES
                agent = make_agent(recorder, index, role)
                agent.night_action(game_state(targets))
                last("night", candidates=targets, role=role.value)

        for index in range(4):
            agent = make_agent(recorder, index, Role.WITCH)
            targets = rng.sample(NAMES[1:], 4)
            agent.witch_action(game_state(targets), "Bob", True, True, targets)
            last("witch", candidates=targets)
    return results


def target_stats(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    exact = parsed = 0
    for row in rows:
        word = clean(row["text"])
        if word in row["candidates"]:
            exact += 1
        if match_player_name(row["text"], row["candidates"]):
            parsed += 1
    n = max(len(rows), 1)
    return {"exact": exact / n, "parsed": parsed / n, "invalid": 1 - parsed / n}


def witch_stats(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    understood = 0
    for row in rows:
        text = row["text"].upper()
        save, poison = parse_witch_answer(row["text"], True, True, row["candidates"])
        if save or poison or "PASS" in text:
            understood += 1
    return {"understood": understood / max(len(rows), 1)}


def discussion_stats(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    texts = [r["text"].strip() for r in rows]
    spoken_rows = [r for r in rows if r["text"].strip() and r["text"].strip().lower().strip(". ") != "no comment"]
    spoken = [r["text"].strip() for r in spoken_rows]
    words = [len(t.split()) for t in spoken] or [0]
    sentences = [len(re.findall(r"[.!?]+(?:\s|$)", t)) or 1 for t in spoken] or [0]
    bigrams = [tuple(zip(t.lower().split(), t.lower().split()[1:])) for t in spoken]
    flat = [b for grams in bigrams for b in grams]
    n = max(len(texts), 1)
    return {
        "no_comment": 1 - len(spoken) / n,
        "role_leak": sum(leaks_own_role(r["text"], r["role"]) for r in spoken_rows) / max(len(spoken_rows), 1),
        "role_word": sum(bool(ROLE_WORDS.search(t)) for t in spoken) / max(len(spoken), 1),
        "names_a_player": sum(any(re.search(rf"\b{n}\b", t) for n in NAMES[1:]) for t in spoken) / max(len(spoken), 1),
        "avg_words": statistics.mean(words),
        "too_long": sum(s > 2 or w > 40 for s, w in zip(sentences, words)) / max(len(spoken), 1),
        "distinct_bigrams": len(set(flat)) / max(len(flat), 1),
        "identical_answers": 1 - len(set(spoken)) / max(len(spoken), 1),
    }


def vram_bytes(host: str, model: str) -> int:
    try:
        for loaded in httpx.get(f"{host}/api/ps", timeout=5).json().get("models", []):
            if loaded.get("name") == model or loaded.get("model") == model:
                return loaded.get("size_vram") or 0
    except httpx.HTTPError:
        pass
    return 0


def unload(host: str, model: str) -> None:
    httpx.post(f"{host}/api/generate", json={"model": model, "keep_alive": 0}, timeout=60)


def benchmark(model: str, host: str, repeats: int, seed: int, num_ctx: int) -> Dict[str, Any]:
    client = OllamaClient(host, model, num_ctx=num_ctx, timeout=600)
    status = client.status()
    if not status["installed"]:
        raise SystemExit(f"{model} is not installed: ollama pull {model}")
    unload(host, model)                       # measure a real cold start
    started = time.monotonic()
    client.generate([Message("user", "Say OK.")], max_tokens=4)
    cold = time.monotonic() - started
    client.reset_metrics()

    results = run_scenarios(client, repeats, seed)
    metrics = client.metrics()
    all_rows = [r for rows in results.values() for r in rows]
    return {
        "model": model,
        "size_gb": round((status["size_bytes"] or 0) / 1e9, 2),
        "vram_gb": round(vram_bytes(host, model) / 1e9, 2),
        "cold_start_s": round(cold, 1),
        "calls": metrics["calls"],
        "errors": metrics["errors"],
        "tokens_per_s": round(metrics["tokens_per_second"], 1),
        "avg_answer_s": round(statistics.mean(r["seconds"] for r in all_rows), 2),
        "avg_prompt_tokens": round(metrics["prompt_tokens"] / max(metrics["calls"], 1)),
        "vote": target_stats(results["vote"]),
        "night": target_stats(results["night"]),
        "witch": witch_stats(results["witch"]),
        "discussion": discussion_stats(results["discussion"]),
        "samples": {
            "discussion": [r["text"].strip() for r in results["discussion"][:6]],
            "vote": [r["text"].strip() for r in results["vote"][:4]],
            "night": [r["text"].strip() for r in results["night"][:4]],
        },
    }


def pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def to_markdown(reports: List[Dict[str, Any]]) -> str:
    head = "| Metric | " + " | ".join(r["model"] for r in reports) + " |\n"
    head += "|---|" + "---|" * len(reports) + "\n"
    rows = [
        ("Download size (GB)", lambda r: r["size_gb"]),
        ("VRAM used (GB)", lambda r: r["vram_gb"]),
        ("Cold start (s)", lambda r: r["cold_start_s"]),
        ("Tokens per second", lambda r: r["tokens_per_s"]),
        ("Seconds per answer", lambda r: r["avg_answer_s"]),
        ("Average prompt tokens", lambda r: r["avg_prompt_tokens"]),
        ("Errors", lambda r: r["errors"]),
        ("Vote: exact name only", lambda r: pct(r["vote"]["exact"])),
        ("Vote: valid after parsing", lambda r: pct(r["vote"]["parsed"])),
        ("Night target: exact name only", lambda r: pct(r["night"]["exact"])),
        ("Night target: valid after parsing", lambda r: pct(r["night"]["parsed"])),
        ("Witch decision understood", lambda r: pct(r["witch"]["understood"])),
        ("Discussion: says 'no comment'", lambda r: pct(r["discussion"]["no_comment"])),
        ("Discussion: states its own role", lambda r: pct(r["discussion"]["role_leak"])),
        ("Discussion: uses a role word at all", lambda r: pct(r["discussion"]["role_word"])),
        ("Discussion: names another player", lambda r: pct(r["discussion"]["names_a_player"])),
        ("Discussion: too long (>2 sentences or >40 words)", lambda r: pct(r["discussion"]["too_long"])),
        ("Discussion: average words", lambda r: f"{r['discussion']['avg_words']:.0f}"),
        ("Discussion: distinct bigrams", lambda r: pct(r["discussion"]["distinct_bigrams"])),
        ("Discussion: identical answers", lambda r: pct(r["discussion"]["identical_answers"])),
    ]
    body = "".join(f"| {name} | " + " | ".join(str(fn(r)) for r in reports) + " |\n" for name, fn in rows)
    samples = ""
    for r in reports:
        samples += f"\n### {r['model']}: sample answers\n\n"
        for kind, texts in r["samples"].items():
            for t in texts:
                samples += f"- *{kind}*: {t.replace(chr(10), ' ')[:300]}\n"
    return head + body + samples


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")   # Windows consoles default to cp1252
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", nargs="+", help="Ollama model tags, e.g. gemma3:1b gemma3:4b")
    parser.add_argument("--host", default=settings.ollama_host)
    parser.add_argument("--repeats", type=int, default=2, help="how many times each scenario set runs")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--num-ctx", type=int, default=settings.llm_num_ctx)
    parser.add_argument("--json", help="write the raw report here")
    parser.add_argument("--markdown", help="write the comparison table here")
    args = parser.parse_args()

    reports = []
    for model in args.models:
        print(f"== {model}", flush=True)
        report = benchmark(model, args.host, args.repeats, args.seed, args.num_ctx)
        print(json.dumps({k: v for k, v in report.items() if k != "samples"}, indent=1), flush=True)
        reports.append(report)
        unload(args.host, model)

    table = to_markdown(reports)
    if args.json:
        Path(args.json).write_text(json.dumps(reports, indent=1), encoding="utf-8")
    if args.markdown:
        Path(args.markdown).write_text(table, encoding="utf-8")
    print(chr(10) + table)


if __name__ == "__main__":
    main()
