# MVP acceptance (Slice 16)

Date: 2026-08-17  
Suite: `66` pytest passed · golden eval PASS (`15` cases)  
Fix applied: setup banner now surfaces `app_dir` (with `env_path`, `missing_key`, `config_path`).

## Slice 16 checklist

| # | Check | Result |
|---|--------|--------|
| 1 | Mock full 10-bug round | **PASS** — start → 10× next/submit → `round_complete`, `round_possible=100`, 10 unique snippets |
| 2 | `/api/health` paths + setup banner | **PASS** — absolute `app_dir` / `env_path` / `config_path`; banner shows those paths + `missing_key` when not ready |
| 3 | Report + `/ops` analyze non-empty | **PASS** — report saved; `POST /api/ops/analyze` returns `report_count≥1`, `round_log_count≥1`, metrics; `/ops` serves |
| 4 | Freshness / degraded path sanity | **PASS** — similarity reject + attempt cap returns canned fallback with `degraded=True` |
| 5 | No answer key on `next-bug` | **PASS** — response omits `bug_summary`, `hints`, `keywords`, `bug_category` |
| 6 | No API keys in frontend | **PASS** — no key material in `web/` (excluding Bootstrap vendor) |
| 7 | Blockers only (no post-MVP) | **PASS** — one UI banner gap fixed; no suggest/apply or other post-MVP work |

## MVP-PLAN success criteria

| Criterion | Result | Notes |
|-----------|--------|-------|
| Complete 10-bug round on localhost without editing app code | **PASS** | Mock provider |
| API keys stay on disk / in the Python process only | **PASS** | Keys only under Application Support / server process |
| Switching `llm.provider` among openai / anthropic / grok works with matching key | **PASS** | Provider modules + 503-without-key + mocked HTTP tests; live keys not required for this pass |
| Documented default provider+model after bakeoff | **WAIVER** | Bakeoff not finished. `config.yaml.example` keeps provisional `openai` / `gpt-4o-mini`; README still says lock after bakeoff |
| Each snippet has one intended bug + usable server-side answer key | **PASS** | Key held in round store; revealed only on submit |
| Within a round, snippets are not near-duplicates | **PASS** | Freshness pipeline + 10/10 unique codes in acceptance mock round |
| Scoring fair enough (lean generous when unsure) | **PASS** | Hybrid + generosity; golden eval 30 good / 30 bad checks |
| Stuck generate fails soft (fallback / clear error) | **PASS** | Canned fallback + `degraded`; UI shows offline-fallback badge / progress text |
| UI usable without frontend build; slow LLM shows progress | **PASS** | Static `web/` + Bootstrap; progress strings for generate / score / prefetch |
| Maintainer can use `/ops` or analyze without hand-reading JSON | **PASS** | Ops dashboard + analyze API/CLI after report + round log |

## Verdict

**MVP complete** (with one documented waiver: lock default provider+model after a live bakeoff).

Out of scope remains as in MVP-PLAN “Later (post-MVP)” — difficulty tracks, suggest/apply, Windows/Linux paths, npm/React, etc.
