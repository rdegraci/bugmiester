# Golden eval

Golden eval is an offline check for Bugmiester scoring. It does not start a round. It does not call OpenAI, Anthropic, or Grok.

Use it when you change keywords, hybrid scoring, or the mock judge. The goal is to catch unfair score changes before you play live rounds.

## What it checks

The case file is `src/bugmiester/eval/golden_cases.json`.

Each case has:

| Field | Meaning |
|-------|---------|
| `id` | Short name for the case |
| `code` | Swift snippet with one bug |
| `expected_summary` | Canonical bug description |
| `bug_category` | Optional category tag |
| `keywords` | Optional scoring keywords |
| `good_answers` | Answers that must get credit |
| `bad_answers` | Answers that must not score as fully correct |

The MVP plan aims for about 20–30 cases. The stub file starts smaller. Add cases when playtesting finds gaps.

## How it works

For each case the runner does this:

1. Score each **good** answer with the keyword scorer.
2. If that answer gets no points, and mock judge is on, score again with hybrid mode plus the mock judge (no network).
3. Fail the case if a good answer still gets zero points.
4. Score each **bad** answer with the keyword scorer.
5. Fail the case if a bad answer is marked fully correct.
6. If mock judge is on, also fail when hybrid + mock judge marks a bad answer fully correct.

The runner prints a short report. Exit code `0` means pass. Exit code `1` means fail.

## How to run

From the repo root, with the package installed (or `PYTHONPATH=src`):

```bash
python -m bugmiester eval
```

Other forms:

```bash
# Machine-readable report
python -m bugmiester eval --json

# Keyword path only (skip mock judge)
python -m bugmiester eval --no-judge

# Pytest wrapper (same checks)
pytest tests/test_golden_eval.py -q
```

## When to run it

- After you change `scoring.py` or keyword lists
- After you change the mock judge
- Before you lock a scoring change from playtest notes
- In local CI or a pre-commit habit if you want a fast offline gate

Do **not** treat this as a live-provider bakeoff. For that, see the bakeoff section in [README.md](../README.md).

## How to add a case

1. Open `src/bugmiester/eval/golden_cases.json`.
2. Copy an existing case object.
3. Set a new `id`, `code`, and `expected_summary`.
4. Add at least one clear `good_answers` entry and one clear `bad_answers` entry.
5. Run `python -m bugmiester eval` and fix failures.

Tips:

- Good answers should name the real bug in plain words.
- Bad answers should name a different bug class (not a vague near-miss of the same bug).
- Keep snippets short. One intentional bug only.

## What it is not

- Not a test of LLM generation quality
- Not a substitute for a full mock or live round
- Not the post-MVP suggest / apply / eval-gate pipeline
- Not required to call live APIs in CI

## Related files

| Path | Role |
|------|------|
| `src/bugmiester/eval/golden_cases.json` | Case data |
| `src/bugmiester/eval/__init__.py` | Loader and runner |
| `tests/test_golden_eval.py` | Pytest entry |
| `src/bugmiester/scoring.py` | Keyword and hybrid scoring |
| `src/bugmiester/llm/mock_provider.py` | Cheap mock judge |
