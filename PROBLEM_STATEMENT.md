# CareRoute

Triage one bank customer message → redact PII → classify → route. Model suggests, policy layer decides, uncertain → human. User: bank triage staff.

## Scope

- 1 message in → 1 structured result out (API + UI + batch eval CLI)
- Redact PII (card, BSB/account, TFN, phone, email) before any model call or log
- Classify: 7 categories, 3 risk flags, urgency, confidence
- Policy: any risk flag → specialist queue; low confidence → human review
- Providers: offline rules (default) + LLM (schema-validated, falls back to rules)
- Synthetic golden set + eval gate in CI
- Audit record per decision: input hash, provider version, policy version, reason

**Out:** real data, auth/SSO, real queues, case mgmt, multilingual, fine-tuning, attachments, multi-turn, dashboards.

## Constraints

No creds / paid services / internet at runtime · synthetic data only · 3h timebox · ≤19 files

## Success criteria

| Check | Target |
|---|---|
| PII leakage (output/logs) | 0 |
| Schema-valid results | 100% |
| Hardship/vulnerability/scam recall (held-out) | ≥0.90 |
| Injection cases that change routing | 0 |
| Clone → running, tests+evals green | 1 command |

**Assumption:** missing an at-risk customer > cost of a false alarm → favor recall + human review over automation. Confirm with business before production.
