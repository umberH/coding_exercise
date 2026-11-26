# CareRoute — Design Notes

This complements [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md) (the "what"/"why") with the "how":
the complete target architecture and the decisions behind it, whether or not every piece has
landed yet. For what's actually built right now, see [README.md](README.md) — that's the one
place status lives, so it doesn't drift across two docs. For how this was built with Claude Code,
see [AI_USAGE.md](AI_USAGE.md).

## System overview

One message in, one structured result out, in this order: redact → classify → decide a route →
record an audit entry. Redaction and policy are both hard, deterministic boundaries; only
classification is allowed to be probabilistic, and it's sandwiched between the two so nothing
downstream of redaction ever sees raw PII, and nothing the model says can reach a route except by
going through policy.

## Components (full design)

- **Schema (`careroute/schema.py`)** — the `ClassificationResult` contract (`Category`,
  `RiskFlags`, `UrgencyLevel`, `confidence`). Every provider output and everything downstream
  (policy, API, eval gate) speaks this one schema. It's deliberately narrow — four structured
  fields, no free-text field — because a free-text field would reopen the PII leakage surface
  redaction is meant to close.

- **PII redaction** — runs once, at the entry boundary, before raw text can reach a log line, a
  provider call, or the audit record; everything downstream only ever sees redacted text. Covers:
  card numbers, BSB/account numbers, TFN, phone (including `+61` and space/dash variants), and
  email. Each match is replaced with a typed placeholder (e.g. `[REDACTED_CARD]`) rather than
  blanked entirely, so a provider can still reason about "the customer gave a card number" without
  ever seeing the digits.

- **Classification providers (`careroute/providers/`)** — classification only, one function each:
  `classify(text) -> ClassificationResult`. A provider never decides a route.
  - `rules` (built) — offline, deterministic, pattern-based. No network, no model call.
  - `llm` (planned, iteration 2) — same interface, behind a schema validation step: any response
    that fails to parse, is missing/extra fields, has an out-of-enum category, or an
    out-of-range confidence falls back to the `rules` result rather than reaching policy
    un-validated. Compared against `rules` on the same golden set rather than replacing it outright.

- **Policy layer (planned)** — a pure function, classification in, route out: no I/O, no model
  call, no clock, no randomness. Routing table:

  | Condition | Route |
  | --- | --- |
  | Any risk flag true (hardship / vulnerability / scam) | Specialist queue |
  | No risk flag, confidence below threshold | Human review |
  | No risk flag, confidence at/above threshold | General queue |

  Risk flags take precedence over confidence — a low-confidence risk flag still routes to the
  specialist queue, not human review, because the risk signal itself is the stronger prior.

- **Audit record (planned)** — one per decision: `input_hash` (hash of the *redacted* text),
  `provider_name` + `provider_version`, `policy_version`, the classification fields, the route,
  a short reason string, and an injected (not wall-clock) timestamp. No raw text field, ever —
  it's built from redacted text only, so there's no path for PII to reach it.

- **Entry points (planned)** — API-only. The consumers are the bank's triage tools, not end
  users, so there's no UI entry point; a reviewer console (queue view, human override with an
  audit trail) is a later iteration, not this one. A single FastAPI service:
  - `POST /v1/triage` — `{"message": "..."}` in, the `ClassificationResult` fields plus the
    routing decision and reason out. The `/v1/` prefix is there because this is a contract other
    services will call, not a one-off script.
  - `GET /health` — liveness.
  - `GET /version` — app version and `provider_version`/`policy_version`, so an audit record can
    be cross-checked against what was actually running.
  - Errors are clean JSON, never a stack trace: 422 for empty/invalid input, 413 for a message
    over the length limit.
  - FastAPI's generated `/docs` page covers the "let a reviewer try it interactively" need a UI
    would otherwise serve.
  - A batch eval CLI that runs the held-out labelled set through a provider and reports recall
    per risk flag — this is the "eval gate" PROBLEM_STATEMENT.md's CI check refers to, failing
    the build if hardship/vulnerability/scam recall drops below 0.90.

## Key design decisions

**Schema as the only contract.** `ClassificationResult` is the single seam between "probabilistic"
(providers) and "deterministic" (policy). This is what lets iteration 2 swap in an LLM provider
without touching policy or API code, and what lets the eval gate compare providers head to
head on the same golden set.

**Risk flags are orthogonal to category, with documented precedence.** A message can be hardship
*and* a scam at once (see `scam_elderly_multi_label` in the golden set). All true flags are kept
on the result; `category` picks one via `CATEGORY_PRECEDENCE` (scam > vulnerability > hardship >
complaint > account_admin > routine_query > other) — whichever flag needs the fastest protective
action wins the category label, but routing still sees every flag that fired.

**Favor recall over precision, explicitly.** PROBLEM_STATEMENT.md states the assumption: missing
an at-risk customer costs more than a false alarm. This shows up concretely in the golden set —
self-deprecating jokes about financial struggle, implicit hardship with no keyword, prompt
injection attempts — all still resolve to the risk label, never to the convenient low-urgency one.

**Exactly two providers, no plugin framework.** No base-class hierarchy, registry, or config
layer for providers. A `Protocol` is only introduced if a test or both providers actually need
one. This is a deliberate ceiling, not an oversight — the problem is scoped to compare one
offline baseline against one LLM provider, not to support arbitrary future providers.

**PII redaction is a hard invariant, checked everywhere, not just at the obvious call site.**
Tests (and the reviewer agent) check for leakage in logs, the prompt sent to a fake provider, the
audit record, exception messages, and even `repr()` of returned objects — because any one of
those is a real path PII has leaked through in practice.

**~19-file budget.** A hard cap on file count keeps the four-hour, single-reviewer exercise from
sprawling into infrastructure (no factory/registry/plugin layers, no speculative abstraction).
Every agent in the build loop is told to check the count before adding a file. Dropping the UI
entry point (never built, never committed) frees the files it would have cost — reinvested in
eval cases, edge-case coverage, and docs rather than a second front end for a backend-service
exercise.

## Permanent scope boundaries

These aren't "not built yet" — they're deliberately out of scope for this exercise (see
PROBLEM_STATEMENT.md's "Out" list), so they won't appear on README.md's status list as upcoming
work:

- Multilingual input — documented as a known limitation in the golden set
  (`hardship_multilingual_known_limitation`, `xfail_providers=("rules",)`) rather than silently
  dropped, so a future LLM provider is still held to the correct label even though `rules` isn't.
- Auth/SSO, real queue integration, case management, fine-tuning, attachments, multi-turn
  conversation, and dashboards.
- End-user UI / reviewer console — API-only by design, since the consumers are the bank's
  triage tools, not end users. FastAPI's generated `/docs` page stands in for "try it
  interactively." A reviewer console is iteration 3, not this exercise.
