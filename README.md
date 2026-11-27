# CareRoute

Triage one bank customer message -> redact PII -> classify -> route.
The classifier suggests, the policy layer decides, and anything uncertain goes to human review.

See [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md) for full scope, success criteria, and what's
deliberately out of scope.

## Status

**Iteration 1, feature-complete for this exercise's time-box.** Built:

- `careroute/schema.py` — the shared `ClassificationResult` contract (category, risk flags,
  urgency, confidence) that every provider and downstream consumer uses.
- `careroute/redaction.py` — offline, deterministic PII redaction (card, BSB/account, TFN,
  phone, email), run before any text reaches a provider, a log line, or the audit record.
- `careroute/providers/rules.py` — the offline, deterministic rules-based classifier
  (no network, no LLM).
- `careroute/policy.py` — the routing decision: any risk flag → specialist queue; no risk flag
  and low confidence → human review; otherwise → general queue.
- `careroute/audit.py` — one audit record per decision (input hash of the *redacted* text,
  provider/policy versions, the classification, the route, a reason), built from redacted text
  only.
- `careroute/pipeline.py` — ties the four stages together in order: redact → classify →
  decide → audit.
- `careroute/cli.py` — the `careroute` command: `careroute triage "<message>"` for one message
  in, one JSON result out, and `careroute eval` as the recall eval gate (see below).
- `.github/workflows/ci.yml` — lint, type-check, unit tests, and the eval gate on every push.
- `tests/golden_set.py` — the shared golden-set fixture the test suite (and the eval gate) are
  driven from.

**Cut from this iteration, deliberately (see [DESIGN.md](DESIGN.md)):**

- **LLM provider.** `PROBLEM_STATEMENT.md` scopes iteration 1 as rules-only from the start —
  this was never pulled forward, not a new cut. The `rules` provider sits behind the same
  interface an LLM provider would, so iteration 2 can add one without touching policy/audit/CLI.
- **HTTP API.** The original design called for a FastAPI service (`POST /v1/triage`, `/health`,
  `/version`). With the time remaining in this exercise's box, a CLI entry point
  (`careroute triage` / `careroute eval`) gives the same "one message in, one structured result
  out" contract at a fraction of the build/test cost (no new dependency, no request/response
  models, no test client). The pipeline the API would have called (`careroute/pipeline.py`)
  is already built and tested, so adding a thin FastAPI wrapper around it later is a small,
  isolated follow-up, not a redesign.
- **Separate held-out eval set.** `PROBLEM_STATEMENT.md` asks for recall measured on a labelled
  set distinct from the regression-only `tests/golden_set.py`. `careroute eval` reuses
  `tests/golden_set.py` instead — building a second labelled set didn't fit the time-box. This
  is flagged in `careroute/cli.py`'s docstring, not silently presented as the real held-out set.

## Try it

```bash
careroute triage "Someone rang pretending to be my bank and got my one-time code, please help."
careroute eval
```

`eval` reports recall per risk flag (hardship/vulnerability/scam) against the golden set and
exits non-zero if any drops below the 0.90 target `PROBLEM_STATEMENT.md` sets — this is the
command `.github/workflows/ci.yml` runs as the CI gate.

## Setup

Requires Python >=3.10.

### bash / Git Bash

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows; use .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"
```

### PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Run

Run the test suite (includes the golden-set classification tests and schema tests):

```bash
pytest
```

Lint and type-check:

```bash
ruff check .
mypy careroute/
```

`pytest` and `ruff check .` are expected to pass clean. `mypy careroute/` is clean under
`strict = true`; running plain `mypy .` instead also picks up the test files, which have
pre-existing missing-annotation errors under strict mode — that's why CI only type-checks
`careroute/`.

## Project layout

```text
careroute/
  schema.py              # ClassificationResult / Category / RiskFlags / UrgencyLevel
  redaction.py            # redact(text) -> text, PII replaced with typed placeholders
  providers/
    rules.py              # offline rules-based classifier: classify(text) -> ClassificationResult
  policy.py               # decide(ClassificationResult) -> RouteDecision
  audit.py                # build_audit_record(AuditInputs) -> AuditRecord
  pipeline.py             # triage(text) -> TriageResult: redact -> classify -> decide -> audit
  cli.py                  # `careroute triage` / `careroute eval` entry points
tests/
  golden_set.py            # shared GOLDEN_CASES fixture, not a test module itself
  test_schema.py
  test_rules_provider.py
  test_golden_set.py       # structural guards on the golden-set fixture
  test_redaction.py
  test_policy.py
  test_audit.py
  test_pipeline.py
  test_cli.py
conftest.py                 # empty; puts repo root on sys.path for pytest
.github/workflows/ci.yml     # lint + type-check + tests + eval gate on every push
```
