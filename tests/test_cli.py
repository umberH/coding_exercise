"""Tests for careroute/cli.py's two subcommands: `triage` and `eval`."""

import json

from careroute.cli import main


def test_triage_command_prints_json_with_classification_route_and_audit(capsys) -> None:
    exit_code = main(["triage", "What's my current account balance?"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["route"] in ("specialist_queue", "human_review", "general_queue")
    assert "category" in payload["classification"]
    assert "input_hash" in payload["audit"]


def test_triage_command_reads_from_stdin_when_no_argument_given(capsys, monkeypatch) -> None:
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("What's my account balance?"))

    exit_code = main(["triage"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert "classification" in payload


def test_eval_command_passes_and_reports_recall_per_risk_flag(capsys) -> None:
    exit_code = main(["eval"])

    output = capsys.readouterr().out
    assert exit_code == 0
    for flag_name in ("hardship", "vulnerability", "scam"):
        assert flag_name in output


def test_eval_command_reports_held_out_set_as_informational_not_gating(capsys) -> None:
    """The held-out set (careroute/held_out_eval_set.py) currently measures
    well below the 0.90 target for this pure pattern-matching provider -
    that's the documented finding motivating an iteration-2 LLM provider,
    not a build failure, so it must be reported (WARN) without affecting
    the exit code."""
    exit_code = main(["eval"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "held-out set" in output
    assert "WARN" in output


def test_eval_command_exits_1_when_golden_set_recall_misses_threshold(monkeypatch, capsys) -> None:
    import careroute.cli as cli_module

    monkeypatch.setattr(cli_module, "_RECALL_THRESHOLD", 1.01)

    exit_code = main(["eval"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "FAIL" in output
