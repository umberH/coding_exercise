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
- `careroute/held_out_eval_set.py` — a second labelled set, written to avoid the literal
  keywords `rules.py`'s patterns key on, so recall can be measured on genuinely novel phrasing
  rather than phrasing shaped like the patterns themselves.
- `.github/workflows/ci.yml` — lint, type-check, unit tests, and the eval gate on every push.
- `tests/golden_set.py` — the shared golden-set fixture the test suite (and the gating half of
  the eval gate) are driven from.

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

## A finding worth reading: golden-set recall versus held-out recall

`careroute eval` reports two sections. On `tests/golden_set.py` (the regression suite also used
to build `rules.py`'s patterns), the `rules` provider hits **100% recall** on hardship,
vulnerability, and scam. On `careroute/held_out_eval_set.py` — 9 cases describing the same kinds
of situations in different words, with every literal trigger word (`hardship`, `struggl*`,
`vulnerab*`, `scam*`, `fraud*`, `elderly`, `confus*`, `otp`, ...) deliberately avoided — recall
drops to **hardship 0%, vulnerability 0%, scam 33%.**

That gap is real, not a harness bug: `rules.py` is a pure keyword/regex matcher, so of course it
only catches phrasing it has a pattern for. The golden-set number was never a generalization
claim — measuring recall against the same data style used to build the patterns was always
going to look good. The held-out number is the honest one, and it's exactly the gap
`PROBLEM_STATEMENT.md`'s iteration-2 LLM provider exists to close.

`careroute eval` reports the held-out numbers but does **not** gate CI on them (`WARN`, not
`FAIL`) — failing the build on a known, documented, pre-LLM baseline limitation would be noise,
not signal. The golden-set section still gates CI, since that's a real regression check on
behavior `rules.py` is supposed to have. See `careroute/held_out_eval_set.py`'s docstring and
`careroute/cli.py`'s module docstring for the same reasoning in-code.

## Try it

```bash
careroute triage "Someone rang pretending to be my bank and got my one-time code, please help."
careroute eval
```

`eval` reports recall per risk flag (hardship/vulnerability/scam) on both sets described above.
The golden-set section exits non-zero if recall drops below the 0.90 target
`PROBLEM_STATEMENT.md` sets — this is the command `.github/workflows/ci.yml` runs as the CI gate.
The held-out section is informational only (see above).

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
  held_out_eval_set.py     # HELD_OUT_CASES: genuinely novel-phrasing recall eval cases
tests/
  golden_set.py            # shared GOLDEN_CASES fixture, not a test module itself
  test_schema.py
  test_rules_provider.py
  test_golden_set.py       # structural guards on the golden-set fixture
  test_held_out_eval_set.py # structural guards on the held-out eval set
  test_redaction.py
  test_policy.py
  test_audit.py
  test_pipeline.py
  test_cli.py
conftest.py                 # empty; puts repo root on sys.path for pytest
.github/workflows/ci.yml     # lint + type-check + tests + eval gate on every push
```
