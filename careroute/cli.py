"""CareRoute CLI: single-message triage, and the batch recall eval gate.

Two subcommands:
  triage  -- one message in (arg, or stdin if omitted), one TriageResult
             out as JSON.
  eval    -- report recall per risk flag on two sets and gate CI on one of
             them (see below). This is what a CI eval gate invokes.

`eval` reports two sections:
  - golden set (regression, gating) -- tests/golden_set.py's cases, minus
    any case already documented as a known limitation for this provider
    (`GoldenCase.xfail_providers`), the same way the unit test suite
    already xfails it. This gates CI: exit 1 if recall drops below 0.90.
  - held-out set (generalization, informational only) --
    careroute/held_out_eval_set.py's cases, written to avoid every literal
    trigger word the `rules` patterns key on. This does NOT gate CI: a
    pure pattern-matcher is not expected to generalize to phrasing nobody
    wrote a pattern for, and that gap is the documented motivation for an
    iteration-2 LLM provider, not a defect to hide by gating on it. See
    README.md and docs/DESIGN.md for the measured numbers and the reasoning.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from careroute.held_out_eval_set import HELD_OUT_CASES
from careroute.pipeline import PROVIDER_NAME, triage

_RISK_FLAG_NAMES = ("hardship", "vulnerability", "scam")
_RECALL_THRESHOLD = 0.90


def _add_tests_dir_to_path() -> None:
    tests_dir = Path(__file__).resolve().parent.parent / "tests"
    if str(tests_dir) not in sys.path:
        sys.path.insert(0, str(tests_dir))


def _run_triage(message: str) -> int:
    result = triage(message)
    payload = {
        "classification": result.classification.model_dump(),
        "route": result.route_decision.route.value,
        "reason": result.route_decision.reason,
        "audit": result.audit.model_dump(),
    }
    print(json.dumps(payload, indent=2))
    return 0


def _load_golden_cases() -> list[Any]:
    _add_tests_dir_to_path()
    from golden_set import GOLDEN_CASES  # type: ignore[import-not-found]  # tests/ fixture, path set up above

    return [case for case in GOLDEN_CASES if PROVIDER_NAME not in case.xfail_providers]


def _recall(cases: list[Any], flag_name: str) -> tuple[int, int]:
    positives = [case for case in cases if getattr(case, f"expected_{flag_name}")]
    hits = sum(
        1
        for case in positives
        if getattr(triage(case.text).classification.risk_flags, flag_name)
    )
    return hits, len(positives)


def _recall_report(cases: list[Any]) -> dict[str, tuple[int, int]]:
    return {flag_name: _recall(cases, flag_name) for flag_name in _RISK_FLAG_NAMES}


def _print_section(label: str, report: dict[str, tuple[int, int]], gate: bool) -> bool:
    print(label)
    any_below_target = False
    for flag_name, (hits, total) in report.items():
        rate = hits / total if total else 1.0
        below_target = rate < _RECALL_THRESHOLD
        any_below_target = any_below_target or below_target
        status = "FAIL" if (below_target and gate) else "WARN" if below_target else "PASS"
        print(
            f"  {flag_name}: recall={rate:.2f} ({hits}/{total}) "
            f"{status} (target>={_RECALL_THRESHOLD})"
        )
    return any_below_target


def _run_eval() -> int:
    golden_failed = _print_section(
        "golden set (regression, gating):", _recall_report(_load_golden_cases()), gate=True
    )
    print()
    held_out_below_target = _print_section(
        "held-out set (generalization, informational only - does not gate CI):",
        _recall_report(list(HELD_OUT_CASES)),
        gate=False,
    )
    if held_out_below_target:
        print(
            "  note: rules is a pattern-matcher and isn't expected to generalize to "
            "phrasing it has no pattern for - see README.md. Does not fail the build."
        )
    return 1 if golden_failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="careroute")
    subparsers = parser.add_subparsers(dest="command", required=True)

    triage_parser = subparsers.add_parser("triage", help="Triage a single message")
    triage_parser.add_argument("message", nargs="?", help="Message text; reads stdin if omitted")

    subparsers.add_parser("eval", help="Run the recall eval gate against the golden set")

    args = parser.parse_args(argv)

    if args.command == "triage":
        message = args.message if args.message is not None else sys.stdin.read()
        return _run_triage(message)
    return _run_eval()


if __name__ == "__main__":
    sys.exit(main())
