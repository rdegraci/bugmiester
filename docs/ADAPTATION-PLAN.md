# Adaptation plan — reinforce isolation before Gnarly

Date: 2026-08-22  
Status: Phase 1 in progress

## Goal

When a player clearly misses **concurrency / isolation** bugs in the **Common** band of a `senior_mix` round, delay **Gnarly** slots and insert **1–2 more Common** bugs from the same concept cluster before the hard costumes. Strong players should see no change from today’s ramp.

## Non-goals

- LLM analysis of free-text answers for curriculum
- Accounts, cloud profiles, or settings UI
- Skipping Gnarly entirely
- Multi-cluster adaptation in v1 (isolation only)
- Cross-round memory until Phase 4

## Player experience (summary)

| Player | Experience |
|--------|------------|
| Strong (0–1 isolation misses in Common) | Same as today: Simple → Common → Gnarly |
| Struggling (2+ clear misses) | One more **Common** isolation bug, then Gnarly (labels stay honest) |
| Phase 3+ | Short banner: “Extra practice on isolation before Gnarly” |

**Clear miss:** incorrect, give-up, or partial with failed recovery. Partial upgraded via recovery does not count.

## Architecture

| Piece | Role |
|-------|------|
| `adaptation.py` | Cluster map, action constants |
| `mix.py` | `adaptive_phase()`, `difficulty_label`, `preferred_categories` |
| `freshness.pick_seed` | Seed draw respects adaptive phase |
| `config.adaptation` | Feature flag and thresholds |
| `metrics` | `bug_category`, `cluster`, `adaptive_action` per bug |
| Phase 4 | `weakness.json` in Application Support |

## Concept clusters (v1)

| Cluster | Categories |
|---------|------------|
| `isolation` | `MainActor`, `sendable`, `concurrency` |

Gnarly costumes (`actor reentrancy`, `exclusivity`, allowlisted seed ids) stay in the Gnarly band, not the isolation reinforcement pool.

## Phases and commits

Each phase is intended as **one reviewable commit** (merge or split as needed).

### Phase 1 — Foundation (no behavior change)

- [x] `docs/ADAPTATION-PLAN.md` (this file)
- [x] `adaptation.py`: clusters, `adaptive_phase()` stub (`enabled=false` → index-only)
- [x] `AdaptationSettings` in config; `config.yaml.example`
- [x] `BugMetrics`: `bug_category`, `cluster`, `adaptive_action`
- [x] Wire metrics on generate; `RoundState.adaptation_enabled`
- [x] `pick_seed` / `difficulty_label` use `adaptive_phase` (default off)
- [x] Tests: clusters, stub phase, config parse, metrics fields

**Exit:** All tests green; live play identical when `adaptation.enabled: false`.

### Phase 2 — Within-round adaptation (MVP)

- [x] Count isolation-cluster **misses** in the Common window (after slop, before reserved gnarly slots)
- [x] If `misses >= miss_threshold` → delay gnarly up to `max_delayed_gnarly` slots
- [x] Reinforcement picks Common isolation seeds (not `is_gnarly_seed()`)
- [x] Set `adaptive_action` to `reinforce` on reinforcement slots
- [x] Unit tests for threshold, cap, strong-player no-op; integration test with mocked miss count

**Exit:** Playable; Gnarly still appears every senior round.

### Phase 3 — Observability + player clarity

- UI banner when reinforcement / delay fires
- Ops / `analyze`: counts of adaptive actions and cluster miss rate
- Tune defaults; flip `adaptation.enabled: true` if metrics look sane

**Exit:** Maintainable; players understand the coach line.

### Phase 4 — Cross-round memory (optional)

- `weakness.json`: cluster hits/misses + decay
- Record on round complete; bias thresholds or first Common slot
- Caps so rounds do not become “10 concurrency bugs”

**Exit:** Multi-session practice without accounts.

## Config (`config.yaml`)

```yaml
adaptation:
  enabled: false              # Phase 1 default; flip in Phase 3
  cluster: isolation            # v1 cluster id
  miss_threshold: 2             # Common-band misses before delay (Phase 2)
  max_delayed_gnarly: 1         # cap delayed gnarly slots per round (Phase 2)
  cross_round: false            # Phase 4
```

## Metrics fields (per bug in round log)

| Field | Values | Phase |
|-------|--------|-------|
| `bug_category` | e.g. `concurrency` | 1 |
| `cluster` | `isolation` or null | 1 |
| `adaptive_action` | `none`, `reinforce`, `delayed_gnarly` | 1 field; values 2+ |

## Success criteria

- Strong players: 0 delayed gnarly slots; ramp matches today
- Struggling players: different isolation **seeds**, same **Common** label, then Gnarly
- No duplicate snippets in one round
- Ops can see when adaptation fires (~10–25% of rounds target, not every round)

## References

- `src/bugmiester/mix.py` — `senior_phase`, mix categories
- `src/bugmiester/freshness.py` — `pick_seed`
- `docs/ACCEPTANCE.md` — MVP gate
