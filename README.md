# Bugmiester

Localhost trainer for Swift bug-spotting.

Each round, an LLM writes **10 short Swift snippets**. Each snippet has **exactly one bug**. You type what the bug is. The app scores your answers (max **100** points per round).

API keys stay on your machine. The browser never sees them.

## Features (MVP)

- Free-text answers (not multiple choice)
- Hybrid scoring: keywords first, then an LLM judge when needed
- Providers: **OpenAI**, **Anthropic**, **Grok** (xAI), plus a **mock** provider for UI work
- Fresh snippets: scenario seeds, avoid-list, similarity reject
- Retry caps, canned fallbacks, and optional next-bug prefetch
- Report bad snippets; local metrics under Application Support
- Ops dashboard at `/ops` to analyze `reports/` and `logs/`
- Offline golden eval stubs for keyword / mock-judge checks
- UI: HTML, local JavaScript, Bootstrap 5 (CSS + bundle JS only)

## Stack

| Layer | Choice |
|-------|--------|
| Frontend | Static HTML / CSS / JS + Bootstrap 5 (vendored) |
| Backend | Python (FastAPI) on `127.0.0.1` |
| Secrets | `.env` in Application Support |
| Settings | `config.yaml` in Application Support |

## Requirements

- macOS (Application Support path for MVP)
- Python 3.11+
- An API key for the provider you select (not needed for `mock`)

## Quick start

1. Clone this repository.
2. Create a virtualenv and install the package:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

3. Start the server:

```bash
python -m bugmiester
```

4. Open [http://127.0.0.1:8765](http://127.0.0.1:8765).
5. On first run the app creates `~/Library/Application Support/Bugmiester/` and copies `.env.example` → `.env` and `config.yaml.example` → `config.yaml` if missing.
6. Put your provider key in `.env`. Set `llm.provider` and `llm.model` in `config.yaml` (start with `mock`).
7. Reload the game page and start a round.

Ops: [http://127.0.0.1:8765/ops](http://127.0.0.1:8765/ops) and `python -m bugmiester analyze`.

## Configuration

### Application Support

| File | Role |
|------|------|
| `.env` | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROK_API_KEY` |
| `config.yaml` | Provider, model, scoring, freshness, server port |
| `reports/` | Player “bad snippet” reports |
| `logs/` | Per-round metrics |

Repo examples (copy sources): `.env.example`, `config.yaml.example`.

### Example `.env`

```bash
OPENAI_API_KEY=replace-me
ANTHROPIC_API_KEY=replace-me
GROK_API_KEY=replace-me
```

Fill the key that matches `llm.provider` in `config.yaml`.

### Example `config.yaml` (shape)

```yaml
llm:
  # Placeholder default — lock provider+model after the bakeoff (see below).
  provider: openai    # openai | anthropic | grok | mock
  model: gpt-4o-mini
  temperature: 0.4
  judge_temperature: 0.0

game:
  bugs_per_round: 10
  language: swift

scoring:
  mode: hybrid
  points_per_bug: 10
  partial_credit: true

server:
  host: 127.0.0.1
  port: 8765
```

Defaults for Grok use the xAI OpenAI-compatible base URL `https://api.x.ai/v1` when `base_url` is null.

**Lock after bakeoff:** Keep `provider` / `model` in `config.yaml.example` and this README as placeholders until you finish the provider bakeoff, then set the chosen default in both places.

## Provider bakeoff

Before polishing UI or calling a live provider “the default,” run the same loop on each backend:

1. **Mock** — full 10-bug round (UI, scoring, reports, ops) with `llm.provider: mock` (no API key).
2. **OpenAI** — set `OPENAI_API_KEY`, `llm.provider: openai`, pick a model (e.g. `gpt-4o-mini`), play one full round.
3. **Anthropic** — set `ANTHROPIC_API_KEY`, `llm.provider: anthropic`, pick a Claude model, play one full round.
4. **Grok** — set `GROK_API_KEY`, `llm.provider: grok`, pick a Grok model (`base_url` defaults to `https://api.x.ai/v1`), play one full round.

Use the same prompts/scoring. Note latency, snippet quality, duplicate feel, and scoring fairness. Then **lock** the winner as the documented default `provider` + `model` in `config.yaml.example` and this README.

CI does **not** require live OpenAI / Anthropic / Grok rounds. Offline golden eval (below) is enough for automated checks.

## Golden eval

Offline stubs live in `src/bugmiester/eval/golden_cases.json` (`code`, `expected_summary`, `good_answers[]`, `bad_answers[]`).

See **[docs/GOLDEN-EVAL.md](docs/GOLDEN-EVAL.md)** for what it checks and how to extend cases.

Run keyword scoring (+ cheap mock judge) against the goldens:

```bash
python -m bugmiester eval
# or
pytest tests/test_golden_eval.py -q
```

Options: `python -m bugmiester eval --json` · `python -m bugmiester eval --no-judge`.

Re-run when you change prompts or scoring. Expand the case file toward ~20–30 as playtesting finds gaps. This is **not** post-MVP suggest/apply automation.

## How a round works

1. Start a round.
2. The server picks a scenario seed and asks the LLM for one buggy Swift snippet.
3. You read the code and type the bug.
4. The server scores your answer and shows the expected summary.
5. Repeat for 10 bugs, then see the round total.

## Documentation

| Doc | Contents |
|-----|----------|
| [docs/cache/MVP-PLAN.md](docs/cache/MVP-PLAN.md) | Product plan, decisions, risks, feedback automation |
| [docs/cache/MVP-DEV.md](docs/cache/MVP-DEV.md) | APIs, layout, config, implementation order |
| [docs/cache/MVP-BUILD_PROMPTS.md](docs/cache/MVP-BUILD_PROMPTS.md) | Cursor build slices for the MVP |
| [docs/GOLDEN-EVAL.md](docs/GOLDEN-EVAL.md) | Offline golden scoring eval: what it does and how to run it |
| [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md) | Slice 16 MVP acceptance checklist (pass/fail) |

## Project layout

```
bugmiester/
  docs/cache/          # MVP plan, dev notes, build prompts
  src/bugmiester/      # Python package (incl. eval/golden_cases.json)
  web/                 # Game + ops UI, vendored Bootstrap
  tests/
  .env.example
  config.yaml.example
  pyproject.toml
```

## License

[MIT](LICENSE) © 2026 Rodney Degracia
