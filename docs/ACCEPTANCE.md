# MVP acceptance (Slice 16 + follow-ups)

Date: 2026-08-20  
Suite: `114` pytest passed · golden eval PASS (`15` cases, `30` good / `30` bad checks)

Slice 16 checklist below remains the MVP gate. Follow-up rows cover work landed after that slice.

## Slice 16 checklist

| # | Check | Result |
|---|--------|--------|
| 1 | Mock full 10-bug round | **PASS** — start → 10× next/submit → `round_complete`, `round_possible=100`, 10 unique snippets |
| 2 | `/api/health` paths + setup banner | **PASS** — absolute `app_dir` / `env_path` / `config_path`; banner shows those paths + `missing_key` when not ready |
| 3 | Report + `/ops` analyze non-empty | **PASS** — report saved; `POST /api/ops/analyze` returns `report_count≥1`, `round_log_count≥1`, metrics; `/ops` serves |
| 4 | Freshness / degraded path sanity | **PASS** — similarity reject + attempt cap returns canned fallback with `degraded=True` |
| 5 | No answer key on `next-bug` | **PASS** — response omits `bug_summary`, `hints`, `keywords`, `bug_category` |
| 6 | No API keys in frontend | **PASS** — no key material in `web/` (excluding Bootstrap vendor) |
| 7 | Blockers only (no post-MVP) | **PASS** — setup banner gap fixed at Slice 16; later features stay within trainer scope (no suggest/apply) |

## MVP-PLAN success criteria

| Criterion | Result | Notes |
|-----------|--------|-------|
| Complete 10-bug round on localhost without editing app code | **PASS** | Mock provider |
| API keys stay on disk / in the Python process only | **PASS** | Keys only under Application Support / server process |
| Switching `llm.provider` among openai / anthropic / xai works with matching key | **PASS** | Provider modules + 503-without-key + mocked HTTP tests; live keys not required for this pass |
| Documented default provider+model after bakeoff | **PASS** | Default locked: `openai` / `gpt-5.6-terra` in `config.yaml.example` and README (live bakeoff still optional for compare) |
| Each snippet has one intended bug + usable server-side answer key | **PASS** | Key held in round store; revealed only on submit (or after recovery) |
| Within a round, snippets are not near-duplicates | **PASS** | Freshness pipeline + 10/10 unique codes in acceptance mock round |
| Scoring fair enough (lean generous when unsure) | **PASS** | Hybrid + generosity; give-up path; golden eval 30 good / 30 bad checks |
| Stuck generate fails soft (fallback / clear error) | **PASS** | Canned fallback + `degraded`; UI shows offline-fallback badge / progress text |
| UI usable without frontend build; slow LLM shows progress | **PASS** | Static `web/` + Bootstrap; progress strings for generate / score / prefetch |
| Maintainer can use `/ops` or analyze without hand-reading JSON | **PASS** | Ops dashboard + analyze API/CLI after report + round log |

## Follow-ups after Slice 16

| Check | Result | Notes |
|-------|--------|-------|
| Round mix + difficulty ramp | **PASS** | Default `senior_mix`: Simple → Common → Gnarly; `difficulty_label` on bug responses |
| Partial-credit recovery quiz | **PASS** | Recovery API + UI; distractors from LLM or seed bank |
| Code view readability | **PASS** | DIY Swift highlighting + line numbers; no `innerHTML` for model code |
| Player-answer hardening | **PASS** | 1000-char cap; fenced untrusted answer in judge/recovery prompts |
| Provider naming | **PASS** | `xai` provider id and `XAI_API_KEY` (not `grok`) |
| OpenAI GPT-5 temperature | **PASS** | Omit / retry without temperature when the API rejects it |
| Gnarly seed depth | **PASS** | Allowlisted hard concurrency / MainActor / exclusivity / reentrancy costumes |

## Verdict

**MVP complete.** Documented default provider and model are locked. Follow-up trainer features above are accepted on the current suite.

Still out of scope (MVP-PLAN “Later”): suggest/apply automation, Windows/Linux Application Support paths, npm/React frontend, live multiplayer.
