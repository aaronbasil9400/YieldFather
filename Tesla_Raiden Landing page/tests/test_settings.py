"""Unit tests for spc_app.settings (JSON session persistence)."""

import json

import pytest

from spc_app import settings


@pytest.fixture()
def settings_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "settings_file", lambda: tmp_path / "settings.json")
    return tmp_path


def test_missing_file_returns_empty_dict(settings_dir):
    assert settings.load_settings() == {}


def test_save_then_load_roundtrip(settings_dir):
    payload = {"last_db": "C:/data/results.db", "selection": {"testnbs": ["12"]}}
    assert settings.save_settings(payload) is True
    assert settings.load_settings() == payload
    raw = json.loads((settings_dir / "settings.json").read_text(encoding="utf-8"))
    assert raw["last_db"] == "C:/data/results.db"


def test_corrupt_file_returns_empty_dict(settings_dir):
    (settings_dir / "settings.json").write_text("{not json", encoding="utf-8")
    assert settings.load_settings() == {}
