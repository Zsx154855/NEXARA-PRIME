"""Factory CLI wiring: enqueue and status reach the durable ledger."""

from __future__ import annotations

import json
from pathlib import Path

from nexara_prime.cli import build_parser, main


def test_parser_exposes_factory_subcommands() -> None:
    args = build_parser().parse_args(["factory", "enqueue", "do the thing"])
    assert args.command == "factory"
    assert args.factory_command == "enqueue"
    assert args.budget == 3


def test_enqueue_then_status_round_trips(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / ".nexara").mkdir()
    monkeypatch.chdir(tmp_path)
    assert main(["factory", "enqueue", "tighten the gate", "--acceptance", "gate is stricter",
                 "--scope", "src"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["state"] == "queued"
    assert payload["epoch"] == 0

    assert main(["factory", "status"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["stats"]["queued"] == 1
    assert status["remote"]["mode"] == "fail-closed"


def test_recover_reports_no_zombies(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / ".nexara").mkdir()
    monkeypatch.chdir(tmp_path)
    assert main(["factory", "recover"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["requeued"] == []
