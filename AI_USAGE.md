# CareRoute — AI-Assisted Development

This documents how Claude Code was used to build CareRoute. For the architecture and design
decisions themselves, see [DESIGN.md](docs/DESIGN.md).

## Why a constrained, multi-agent loop

Claude Code did the implementation, under a deliberately tight, human-written spec — the opposite
of "describe the feature and let the agent figure it out." Three things drove that choice:

- The problem is safety-sensitive — missed hardship/vulnerability/scam signals have real
  consequences, so the behavior that matters most is exactly the kind an agent could plausibly
  get subtly wrong without a human-authored spec and golden set holding it to account.
- PII handling has zero tolerance for leaks — a single missed redaction path is a fail, so the
  checks for it needed to be explicit and repeated on every change, not trusted to "the model
  will remember."
- Dependency choice needed the same tight leash — no new runtime dependencies, no network calls
  at runtime, stdlib or whatever `pyproject.toml` already declares (just `pydantic`) only. Left
  unconstrained, an agent routinely reaches for a new library to solve a problem the stdlib
  already handles, which is its own kind of scope creep.

## The four-agent loop

Defined in `.claude/agents/`, each with a narrow job and its own hard boundaries:

1. **`careroute-tester`** writes the failing tests for one feature, before any implementation
   exists — tests are the spec and the contract the implementation is held to. It derives cases
   from the problem statement and the shared golden-set fixture, traces every test to a
   requirement ID (e.g. `REQ-ROUTE-02`), and is explicitly told to push back — list the possible
   readings and ask — rather than encode a guessed label when the spec is ambiguous. It never
   implements behavior; the only non-test code it may write is a typed interface stub that raises
   `NotImplementedError`.
2. **`careroute-python-expert`** turns red tests green with the smallest diff. It cannot touch
   `tests/`, must flag (not silently fix) anything it thinks is wrong with a test, and works
   under measurable code-shape limits (function length, nesting depth, arg count) instead of
   vibes-based "keep it clean" guidance. It's also told to push back if a test demands something
   unsafe or needlessly complex, rather than just making it pass.
3. **`careroute-builder`** is the one-feature-at-a-time implementer for anything that doesn't
   split cleanly into the tester/expert pairing — same one-feature, tests-first, file-budget
   discipline, and the same instruction to produce a diff reviewable in under a minute.
4. **`careroute-reviewer`** adversarially checks every diff against a fixed, ordered checklist —
   tests actually cover the change, PII discipline, schema validation, policy-layer determinism,
   scope, file budget, diff size — and reports a hard pass/fail per check, not prose, stopping at
   the first hard failure. It runs after every change, not just at the end: the working
   assumption is that AI-written code needs AI review on every change, the same way it would need
   human review on every change.

## Why this shape instead of one agent doing everything

Separating "write the test" from "make it pass" is the same reason TDD helps with human-written
code — it forces the behavioral contract to be stated before the implementation can rationalize
around whatever it happened to write. Routing every diff through a reviewer with a fixed,
ordered checklist catches the specific failure modes this problem is most exposed to — a
redaction path that missed a log line, a provider output that reached a route without going
through policy — rather than relying on a single pass to remember every invariant at once.

## Golden-set-driven, not ad hoc

`tests/golden_set.py` is a single shared fixture (~16 labelled cases, each with a rationale and
tags: implicit, negation, multi-label, injection, known-limitation) that unit tests and, later,
the recall-eval gate both draw from. Agents were told to explore candidate cases widely but keep
only the ones that prove something no existing case already proves, rather than growing the
suite indefinitely — a bloated suite is treated as much a failure as a missing test.

## What stayed a human decision, not an agent one

The problem scope and success criteria (`PROBLEM_STATEMENT.md`), the category-precedence and
urgency-escalation policy, the recall-over-precision tradeoff, and anything the tester or
python-expert agents flagged as ambiguous were all resolved by the author, not guessed by an
agent. The agents' job was to implement a fully-specified contract quickly and correctly, not to
make the judgment calls the problem is actually testing.

## Agent definition history

The agent prompts themselves were iterated on before any feature code existed
(`12ca76b` adds the initial builder/reviewer pair, `20b092e` adds the tester/python-expert split,
`00116bf` tightens all four against a stricter guideline) — the loop's shape was a deliberate
upfront decision, not something that emerged ad hoc while building features.
