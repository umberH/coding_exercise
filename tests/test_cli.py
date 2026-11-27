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
