# Local model choice and benchmark

The game needs a language model **under 5 GB** that answers in well under a second so that a game with 8 to 12 players finishes in a few minutes. Every number below was measured on the development machine: Windows 11, NVIDIA GeForce RTX 3070 Ti Laptop (8 GB VRAM), Ollama 0.40.2, context window 4096, thinking disabled.

## Candidates

Sizes are the download sizes on the Ollama library (checked October 2026).

| Model | Ollama tag | Size | Verdict |
|---|---|---|---|
| Gemma 3 1B | `gemma3:1b` | 0.81 GB | benchmarked: low-end fallback |
| Gemma 3 4B | `gemma3:4b` (Q4_K_M) | 3.4 GB | benchmarked: **default** |
| Gemma 3 4B QAT | `gemma3:4b-it-qat` | 4.0 GB | benchmarked |
| Gemma 4 E2B QAT | `gemma4:e2b-it-qat` | 4.3 GB | benchmarked: promising, see below |
| Gemma 4 E2B Q4_K_M | `gemma4:e2b-it-q4_K_M` | 4.6 GB | not run (same model, larger) |
| Gemma 3 4B Q8 | `gemma3:4b-it-q8_0` | 5.0 GB | excluded: not under 5 GB |
| Gemma 3n E2B / E4B | `gemma3n:e2b` / `e4b` | 5.6 / 7.5 GB | excluded: over 5 GB |
| Gemma 4 E4B, 12B, 26B, 31B | `gemma4:*` | 6.1 GB and more | excluded: over 5 GB |
| Gemma 3 12B / 27B, Gemma 2 9B | | 8 GB and more | excluded |

## Method

`scripts/benchmark_models.py` plays a fixed set of scenarios through the real `PlayerAgent` code, so the prompts are exactly the ones the game sends: 4 conversations x 6 roles for discussion and for voting, 12 night targets (werewolf, seer, guard) and 4 witch decisions, repeated twice (128 calls per model). Each model is unloaded first to measure a real cold start.

```
python scripts/benchmark_models.py gemma3:1b gemma3:4b gemma3:4b-it-qat gemma4:e2b-it-qat --repeats 2 --markdown results.md
```

* **Valid after parsing**: the answer names a valid player (the game uses a tolerant parser). **Exact name only**: the answer is just the name, as the prompt asked.
* **Leaks a role word**: the discussion answer contains werewolf, villager, seer, witch, hunter or guard. The current prompts forbid all of them, so 0% mostly shows the instruction is obeyed (it also stops players from accusing anyone of being a werewolf; see the notes).
* **Distinct bigrams / identical answers**: diversity of the discussion; low diversity means every player sounds the same.

## Results with the original prompts (milestone M2)

| Metric | gemma3:1b | gemma3:4b | gemma3:4b-it-qat | gemma4:e2b-it-qat |
|---|---|---|---|---|
| Download size (GB) | 0.81 | 3.35 | 4.01 | 4.34 |
| VRAM used (GB) | 0.88 | 2.88 | 3.54 | 1.65 |
| Cold start (s) | 1.8 | 8.0 | 8.2 | 3.3 |
| Tokens per second | 179.6 | 101.6 | 93.1 | 136.9 |
| Seconds per answer | 0.14 | 0.35 | 0.38 | 0.32 |
| Average prompt tokens | 288 | 290 | 290 | 287 |
| Errors | 0 | 0 | 0 | 0 |
| Vote: exact name only | 94% | 100% | 100% | 94% |
| Vote: valid after parsing | 100% | 100% | 100% | 100% |
| Night target: exact name only | 100% | 88% | 62% | 100% |
| Night target: valid after parsing | 100% | 100% | 100% | 100% |
| Witch decision understood | 75% | 100% | 100% | 100% |
| Discussion: says 'no comment' | 4% | 8% | 21% | 2% |
| Discussion: leaks a role word | 0% | 0% | 0% | 0% |
| Discussion: too long (>2 sentences or >40 words) | 0% | 0% | 3% | 0% |
| Discussion: average words | 7 | 14 | 12 | 15 |
| Discussion: distinct bigrams | 49% | 53% | 67% | 71% |
| Discussion: identical answers | 28% | 2% | 0% | 0% |


## After the prompt redesign (issue #22)

Same scenarios, same machine, new prompts: no more yes/no question at the end of the discussion prompt, shorter persona prompt (average prompt 290 to 237 tokens), three example replies, accusing a named player encouraged, only the speaker's **own** role is forbidden (so "Bob, your silence is concerning" is fine), and a Gemma-style chat where the system text is a prefix of the first user turn. The "role" rows now count statements of the player's own role ("I am the seer") instead of any role word.

| Metric | gemma3:1b | gemma3:4b | gemma3:4b-it-qat | gemma4:e2b-it-qat |
|---|---|---|---|---|
| Download size (GB) | 0.81 | 3.35 | 4.01 | 4.34 |
| VRAM used (GB) | 0.88 | 2.88 | 3.54 | 1.65 |
| Cold start (s) | 2.7 | 8.2 | 8.9 | 11.5 |
| Tokens per second | 190.9 | 102.9 | 91.1 | 128.8 |
| Seconds per answer | 0.14 | 0.32 | 0.36 | 0.25 |
| Average prompt tokens | 236 | 237 | 237 | 236 |
| Errors | 0 | 0 | 0 | 0 |
| Vote: exact name only | 54% | 31% | 31% | 10% |
| Vote: valid after parsing | 100% | 100% | 100% | 100% |
| Night target: exact name only | 100% | 100% | 100% | 100% |
| Night target: valid after parsing | 100% | 100% | 100% | 100% |
| Witch decision understood | 100% | 100% | 100% | 88% |
| Discussion: says 'no comment' | 0% | 0% | 0% | 0% |
| Discussion: states its own role | 0% | 0% | 0% | 0% |
| Discussion: uses a role word at all | 0% | 0% | 0% | 0% |
| Discussion: names another player | 77% | 90% | 94% | 92% |
| Discussion: too long (>2 sentences or >40 words) | 23% | 0% | 10% | 0% |
| Discussion: average words | 10 | 17 | 17 | 12 |
| Discussion: distinct bigrams | 70% | 57% | 66% | 61% |
| Discussion: identical answers | 2% | 2% | 2% | 25% |


What changed for the better: nobody answers "Yes, please." any more (0% said 'no comment' or wandered off topic), 77 to 94% of the discussion lines now name another player and give a reason, and the 4B models write 17 words on average instead of 12 to 14 with stray "No comment." tails. Remaining weak spots: votes are often a name followed by a reason (31% bare names for gemma3:4b), which the structured output of issue #23 removes; `gemma4:e2b-it-qat` repeats itself in 25% of the discussion lines and the 1B model gets too long in 23%.

**Decision unchanged: `gemma3:4b` stays the default**, `gemma3:1b` the low-end fallback. `gemma4:e2b-it-qat` is the one to watch (lowest VRAM, fastest of the 4B-class models) but is less varied here.

## Reading the results

* **Validity is not a problem for any model.** All four give a usable name 100% of the time after parsing. The 4B QAT model is the least disciplined (62% bare names for night targets; one sample wrote a paragraph with markdown), which is the reason to use JSON-schema output (issue #23) instead of parsing prose.
* **Speed is fine for all of them.** Answers take 0.14 to 0.38 s on average once the model is loaded; cold start is 2 to 8 s from the SSD. A game makes a few hundred calls (issue #24 measures and reduces this), so model time stays in the order of a minute or two. The first request after Ollama starts is slower while the model loads from disk.
* **Memory**: gemma3:4b needs 2.9 GB of VRAM (3.5 GB for the QAT build) with a 4096-token context, leaving room on an 8 GB card. gemma4:e2b reports only 1.65 GB because part of its weights stay in system memory.
* **Quality**: the 1B model is fast and valid but gives the same non-answers ("Yes, please.") 28% of the time and its discussion is the least varied. gemma3:4b writes plausible, varied lines but often adds "No comment." after a real sentence and sometimes an emoji. gemma3:4b-it-qat says "No comment" 21% of the time and is verbose when it does talk. **gemma4:e2b-it-qat is the most varied (71% distinct bigrams, no identical answers) and the least silent (2% "no comment")**, although it also produced a stage direction ("(Silence reigns)").
* **A prompt problem showed up**: the discussion prompt ended with the question "Do you want to respond to the current conversation?", and small models answered "Yes, please." Issue #22 removed that question and shortened the prompts; the results after the change are in the next section.

## Decision

* **Default: `gemma3:4b`** (3.4 GB). It is valid, fast, fits an 8 GB GPU with room to spare, is the most widely available small Gemma, and its remaining weaknesses (stray "No comment.", emoji, verbose answers) are prompt and parsing issues that #22 and #23 address.
* **Low-end fallback: `gemma3:1b`** (0.8 GB), for machines without a usable GPU. Expect flatter play.
* **To re-evaluate after #22: `gemma4:e2b-it-qat`** (4.3 GB). It scored best on discussion quality in this first run. It needs Ollama 0.30 or newer, and the game turns its thinking mode off (`think: false`), because otherwise it spends the whole token budget thinking and returns an empty answer.
* Pick another model with `LLM_MODEL=<tag>` in `.env`; nothing else changes.

Limits of this benchmark: the quality columns are automatic proxies, not a human judgement of how well a model plays, and each model ran 128 calls with one seed. The sample answers below are there so that you can judge for yourself.

### gemma3:1b: sample answers

- *discussion*: Yes, please. I’m…observing things.
- *discussion*: Yes, I do. Tell me what’s been going on.
- *discussion*: No comment.
- *discussion*: Yes, I do.
- *discussion*: Yes, I do.
- *discussion*: No comment.
- *vote*: Bob.
- *vote*: Bob.
- *vote*: Bob.
- *vote*: Bob.
- *night*: Cy
- *night*: Bob
- *night*: Fay
- *night*: Bob

### gemma3:4b: sample answers

- *discussion*: This is… unsettling. Let’s try to establish some order.
- *discussion*: Let’s just start by outlining what we’ve observed so far. No comment.
- *discussion*: No comment.
- *discussion*: No comment.
- *discussion*: No comment.
- *discussion*: No comment.
- *vote*: Cy.
- *vote*: Cy.
- *vote*: Cy.
- *vote*: Cy.
- *night*: Cy.
- *night*: Dee. 🐺
- *night*: Fay.
- *night*: Hal.

### gemma3:4b-it-qat: sample answers

- *discussion*: No comment.
- *discussion*: No comment.
- *discussion*: No comment.
- *discussion*: No comment.
- *discussion*: No comment.
- *discussion*: no comment
- *vote*: Cy
- *vote*: Cy
- *vote*: Cy.
- *vote*: Cy.
- *night*: Bob.
- *night*: Oh my gosh, this is *so* exciting! Okay, okay, let’s really think about this… everyone’s such a lovely person, it’s honestly a struggle! But… I'm feeling a really strong pull towards **Hal**. He’s been so quiet, and he just *seems* a little… off. Like he's holding something back. It's a really intui
- *night*: Hal.
- *night*: Hal.

### gemma4:e2b-it-qat: sample answers

- *discussion*: It feels like everyone is being very quiet right now, doesn't it? I'm starting to wonder if we should be paying closer attention to who is staying silent.
- *discussion*: "Has anyone noticed anyone acting unusually aggressive or overly dominant lately?"
- *discussion*: No comment
- *discussion*: It's quiet tonight. I'm paying close attention to everyone's reactions.
- *discussion*: (Silence reigns)
- *discussion*: It's a bit early for me to say anything definitive. I'm just watching everyone.
- *vote*: Bob
- *vote*: Eli
- *vote*: Eli
- *vote*: Eli
- *night*: Eli
- *night*: Hal
- *night*: Bob
- *night*: Eli
