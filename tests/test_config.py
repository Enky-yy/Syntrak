"""Tests for configuration loading and workspace root resolution."""

import os
from pathlib import Path
import pytest
import yaml
from syntrak.config import SyntrakConfig


def test_default_workspace_root():
    cfg = SyntrakConfig.load()
    assert Path(cfg.workspace_root).resolve() == Path(os.getcwd()).resolve()


def test_custom_workspace_root(tmp_path):
    custom_ws = tmp_path / "custom_project"
    custom_ws.mkdir()
    cfg = SyntrakConfig.load(workspace_root=str(custom_ws))
    assert Path(cfg.workspace_root).resolve() == custom_ws.resolve()


def test_save_global_omits_workspace_root(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cfg = SyntrakConfig(workspace_root="/some/temp/project")
    dest = cfg.save_global()

    assert dest.is_file()
    with open(dest, "r", encoding="utf-8") as f:
        saved_data = yaml.safe_load(f)

    assert "workspace_root" not in saved_data


def test_env_file_loading(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "GOOGLE_CLIENT_ID=test-google-client-id-123.apps.googleusercontent.com\n"
        "LLM_MODEL=openai/gpt-4o\n"
        "OPENAI_API_KEY=sk-test-secret-key\n",
        encoding="utf-8"
    )

    cfg = SyntrakConfig.load(env_file=str(env_file), workspace_root=str(tmp_path))
    assert cfg.google_client_id == "test-google-client-id-123.apps.googleusercontent.com"
    assert cfg.llm.model == "openai/gpt-4o"
    assert cfg.llm.api_key == "sk-test-secret-key"
