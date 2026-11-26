## Problem
Triage one bank customer message → redact PII → classify → route.
The classifier suggests, the policy layer decides, uncertain → human review.
User: bank triage staff.

## Iteration 1 scope
Rules-based classifier only. No LLM, no network, no credentials.
The classifier sits behind a single interface so an LLM can be added in iteration 2
and compared against this baseline using the same golden set and eval gate.

## Scope

- 1 message in → 1 structured result out (API + UI + batch eval CLI)
- Redact PII (card, BSB/account, TFN, phone, email) before any model call or log
- Classify: 7 categories, 3 risk flags, urgency, confidence
- Policy: any risk flag → specialist queue; low confidence → human review
- Providers: offline rules (default) + LLM (schema-validated, falls back to rules)
- Synthetic golden set + eval gate in CI
- Audit record per decision: input hash, provider version, policy version, reason

**Out:** real data, auth/SSO, real queues, case mgmt, multilingual, fine-tuning, attachments, multi-turn, dashboards.


## Success criteria

| Check | Target |
|---|---|
| PII leakage (output/logs) | 0 |
| Schema-valid results | 100% |
| Hardship/vulnerability/scam recall (held-out) | ≥0.90 |
| Injection cases that change routing | 0 |
| Clone → running, tests+evals green | 1 command |

**Assumption:** missing an at-risk customer > cost of a false alarm → favor recall + human review over automation. Confirm with business before production.
