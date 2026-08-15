# Bugmiester

Localhost trainer for Swift bug-spotting.

Each round, an LLM writes **10 short Swift snippets**. Each snippet has **exactly one bug**. You type what the bug is. The app scores your answers (max **100** points per round).

API keys stay on your machine. The browser never sees them.

> **Status:** MVP is specified in `docs/cache/`. Slice 01 skeleton is in place (`src/bugmiester/`, example config). Server and UI come in later slices.

## Features (MVP)

- Free-text answers (not multiple choice)
- Hybrid scoring: keywords first, then an LLM judge when needed
- Providers: **OpenAI**, **Anthropic**, **Grok** (xAI), plus a **mock** provider for UI work
- Fresh snippets: scenario seeds, avoid-list, similarity reject
- Retry caps and canned fallbacks when generation fails
- Report bad snippets; local metrics under Application Support
- Ops dashboard at `/ops` to analyze `reports/` and `logs/`
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
- Python 3.11+ (planned)
- An API key for the provider you select (not needed for `mock`)

## Quick start

1. Clone this repository.
2. Create a virtualenv and install the package:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

3. Run the module:

```bash
python -m bugmiester
```

Slice 01 prints a stub message. Later slices start the server on `127.0.0.1:8765`.

When the server exists:

4. Open [http://127.0.0.1:8765](http://127.0.0.1:8765).
5. On first run the app creates `~/Library/Application Support/Bugmiester/` and copies `.env.example` → `.env` and `config.yaml.example` → `config.yaml` if missing.
6. Put your provider key in `.env`. Set `llm.provider` and `llm.model` in `config.yaml`.
7. Reload the game page and start a round.

Ops (later slices): [http://127.0.0.1:8765/ops](http://127.0.0.1:8765/ops) and `python -m bugmiester analyze`.

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

## Project layout

```
bugmiester/
  docs/cache/          # MVP plan, dev notes, build prompts
  src/bugmiester/      # Python package (stubs → features by slice)
  web/                 # Game + ops UI, vendored Bootstrap (Slice 03+)
  .env.example
  config.yaml.example
  pyproject.toml
```

## License

[MIT](LICENSE) © 2026 Rodney Degracia
