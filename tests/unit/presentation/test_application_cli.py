import argparse
import builtins

from src.presentation.cli.application import Application


def test_application_no_args_returns_help(monkeypatch):
    # Avoid printing to console
    monkeypatch.setattr(builtins, 'print', lambda *a, **k: None)
    app = Application()
    code = app.run([])
    assert code == 1


def test_application_unknown_command(monkeypatch):
    app = Application()
    import pytest
    with pytest.raises(SystemExit):
        app.run(['unknown'])
