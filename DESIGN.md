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
    un-validated. The same fallback applies if the call itself errors or times out — in every
    case, policy always receives a valid `ClassificationResult` (the LLM's or the `rules`
    fallback), and routing proceeds normally from there. There is no path where a classification
    failure routes directly to human review bypassing policy; a classification failure instead
    becomes a `rules`-provider result, which the usual confidence/risk-flag logic may or may not
    send to human review. Compared against `rules` on the same golden set rather than replacing
    it outright.

- **Policy layer (built, `careroute/policy.py`)** — a pure function, classification in, route
  out: no I/O, no model call, no clock, no randomness. Routing table:

  | Condition | Route |
  | --- | --- |
  | Any risk flag true (hardship / vulnerability / scam) | Specialist queue |
  | No risk flag, confidence below threshold (0.7) | Human review |
  | No risk flag, confidence at/above threshold | General queue |

  Risk flags take precedence over confidence — a low-confidence risk flag still routes to the
  specialist queue, not human review, because the risk signal itself is the stronger prior. The
  0.7 threshold sits strictly between the `rules` provider's two confidence values (0.9 for a
  recognized category, 0.4 for `OTHER`), so every `OTHER` result lands in human review and every
  recognized category clears straight to the general queue unless a risk flag overrides it.

- **Audit record (built, `careroute/audit.py`)** — one per decision: `input_hash` (SHA-256 of
  the *redacted* text), `provider_name` + `provider_version`, `policy_version`, the full
  classification, the route, and a reason string. `build_audit_record` takes a single
  `AuditInputs` bundle (to stay inside this project's 3-argument function-signature limit) built
  only from already-redacted text — there is no parameter on either type that accepts raw text,
  so there's no path for PII to reach it by construction. No wall-clock timestamp: a pure
  function can't call one, and injecting one would need a clock dependency this iteration
  doesn't have a use for yet.

- **Pipeline (built, `careroute/pipeline.py`)** — the single `triage(text) -> TriageResult`
  function that sequences the four stages above in order and is what every entry point (CLI now,
  an HTTP API later) calls. This is the seam that makes "redact before classify before policy
  before audit" an invariant of the code path rather than a convention callers have to remember.

- **Entry points — CLI built now, HTTP API deferred.** The original design (below) called for a
  FastAPI service as the only entry point, with no UI. Given this exercise's time-box, a CLI
  (`careroute/cli.py`) was built instead of the API first — same "one message in, one structured
  result out" contract, calling the same `pipeline.triage`, at much lower build/test cost. This
  is a sequencing decision, not a reversal: the API remains the target for a non-time-boxed
  iteration 2, and because `pipeline.py` already exists and is tested, adding it is wrapping
  `triage()` in request/response handling, not rebuilding the triage logic.
  - `careroute triage "<message>"` (or stdin) — one message in, the `TriageResult` (classification,
    route, reason, and audit record) out as JSON.
  - `careroute eval` — runs `tests/golden_set.py`'s cases through the pipeline and reports recall
    per risk flag, excluding cases already marked `xfail_providers=("rules",)` (the same
    known-limitation exclusion the unit tests already apply); exits 1 if hardship/vulnerability/
    scam recall drops below 0.90. This is the "eval gate" PROBLEM_STATEMENT.md's CI check refers
    to, and what `.github/workflows/ci.yml` runs on every push.
  - **Still planned, not built:** the FastAPI service itself (`POST /v1/triage`, `GET /health`,
    `GET /version`, JSON error responses, FastAPI's `/docs` page standing in for "try it
    interactively"). Design intent unchanged from the original notes below; only the build order
    changed.

## Key design decisions

**Golden-set recall and held-out recall are reported separately, and only one gates CI.**
`careroute/held_out_eval_set.py` holds 9 cases describing the same hardship/vulnerability/scam
situations as the golden set, phrased to avoid every literal trigger word `rules.py`'s patterns
key on. Measured recall on it is far below the golden set's (0%/0%/33% vs. 100%/100%/100%) -
expected for a pure pattern-matcher, and exactly the gap an iteration-2 LLM provider exists to
close. `careroute eval` reports both but only gates the build on the golden-set section
(`WARN`, not `FAIL`, for held-out misses) - failing CI on a known, already-documented baseline
limitation would be noise, not a real regression signal. See README.md's "golden-set recall
versus held-out recall" section for the full numbers and reasoning.

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
