"""Security-hardening tests for cognidb.config (Module-A, Contract 5).

Covers four confirmed audit findings:
  1. Per-install random salt + OWASP-strength KDF for file-based secrets.
  2. Secret dataclass fields excluded from ``repr``.
  3. ``${ENV_VAR}`` placeholder expansion on config load (fail loud when unset).
  4. No secret is ever emitted to logs by this module.
"""

from __future__ import annotations

import json
import logging
import os
import stat
from pathlib import Path

import pytest

from cognidb.config import secrets as secrets_module
from cognidb.config.secrets import SecretsManager
from cognidb.config.loader import ConfigLoader
from cognidb.config.settings import (
    CacheConfig,
    CacheProvider,
    DatabaseConfig,
    DatabaseType,
    LLMConfig,
    LLMProvider,
    SecurityConfig,
)
from cognidb.core.exceptions import ConfigurationError


# ---------------------------------------------------------------------------
# Fix 1 — per-install random salt + strong KDF
# ---------------------------------------------------------------------------

MASTER_PASSWORD = "correct horse battery staple"


def _file_manager(path: Path) -> SecretsManager:
    """Build a file-backed SecretsManager rooted at ``path``."""
    return SecretsManager(
        provider="file",
        secrets_file=str(path),
        master_password=MASTER_PASSWORD,
    )


def test_kdf_iterations_meet_owasp_minimum() -> None:
    assert secrets_module.KDF_ITERATIONS >= 600_000


def test_fresh_installs_produce_different_salts(tmp_path: Path) -> None:
    sm_a = _file_manager(tmp_path / "a" / "secrets.enc")
    sm_b = _file_manager(tmp_path / "b" / "secrets.enc")

    assert sm_a._salt != sm_b._salt
    assert len(sm_a._salt) >= 16


def test_secret_round_trips_across_restart(tmp_path: Path) -> None:
    secrets_file = tmp_path / "secrets.enc"

    writer = _file_manager(secrets_file)
    writer.set_secret("DB_PASSWORD", "s3cr3t-value")

    # Simulate a process restart: a brand-new manager over the same file.
    reader = _file_manager(secrets_file)
    assert reader.get_secret("DB_PASSWORD") == "s3cr3t-value"


def test_secrets_file_persists_salt_envelope(tmp_path: Path) -> None:
    secrets_file = tmp_path / "secrets.enc"
    sm = _file_manager(secrets_file)
    sm.set_secret("API", "abc")

    envelope = json.loads(secrets_file.read_text())
    assert set(envelope) >= {"salt", "ciphertext"}
    # Persisted salt must match the manager's in-memory salt.
    assert bytes.fromhex(envelope["salt"]) == sm._salt
    # Ciphertext must not leak the plaintext value.
    assert "abc" not in envelope["ciphertext"]


def test_secrets_file_has_0600_permissions(tmp_path: Path) -> None:
    secrets_file = tmp_path / "secrets.enc"
    sm = _file_manager(secrets_file)
    sm.set_secret("API", "abc")

    mode = stat.S_IMODE(os.stat(secrets_file).st_mode)
    assert mode == 0o600


def test_tampered_ciphertext_fails(tmp_path: Path) -> None:
    secrets_file = tmp_path / "secrets.enc"
    writer = _file_manager(secrets_file)
    writer.set_secret("DB_PASSWORD", "s3cr3t-value")

    envelope = json.loads(secrets_file.read_text())
    ciphertext = envelope["ciphertext"]
    # Flip a character to corrupt the authenticated ciphertext.
    flipped = "A" if ciphertext[0] != "A" else "B"
    envelope["ciphertext"] = flipped + ciphertext[1:]
    secrets_file.write_text(json.dumps(envelope))

    with pytest.raises(ConfigurationError):
        _file_manager(secrets_file)


# ---------------------------------------------------------------------------
# Fix 2 — secrets excluded from repr
# ---------------------------------------------------------------------------


def test_database_config_password_not_in_repr() -> None:
    secret = "pg-super-secret"
    cfg = DatabaseConfig(
        type=DatabaseType.POSTGRESQL,
        host="localhost",
        port=5432,
        database="db",
        username="user",
        password=secret,
    )
    assert secret not in repr(cfg)
    assert cfg.password == secret


def test_llm_config_api_key_not_in_repr() -> None:
    secret = "sk-live-abcdef"
    cfg = LLMConfig(provider=LLMProvider.OPENAI, api_key=secret)
    assert secret not in repr(cfg)
    assert cfg.api_key == secret


def test_cache_config_redis_password_not_in_repr() -> None:
    secret = "redis-secret-pw"
    cfg = CacheConfig(provider=CacheProvider.REDIS, redis_password=secret)
    assert secret not in repr(cfg)
    assert cfg.redis_password == secret


def test_security_config_encryption_key_not_in_repr() -> None:
    secret = "enc-key-material"
    cfg = SecurityConfig(encryption_key=secret)
    assert secret not in repr(cfg)
    assert cfg.encryption_key == secret


# ---------------------------------------------------------------------------
# Fix 3 — ${ENV_VAR} expansion on config load
# ---------------------------------------------------------------------------


def _loader() -> ConfigLoader:
    # config_file=None keeps discovery from picking up a real file.
    return ConfigLoader(config_file="")


def test_expand_env_var_resolves_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("FOO", "bar")
    result = _loader()._expand_env_vars({"password": "${FOO}"})
    assert result == {"password": "bar"}


def test_expand_env_var_unset_raises(monkeypatch) -> None:
    monkeypatch.delenv("DEFINITELY_UNSET_VAR", raising=False)
    with pytest.raises(ConfigurationError) as exc:
        _loader()._expand_env_vars({"password": "${DEFINITELY_UNSET_VAR}"})
    assert "DEFINITELY_UNSET_VAR" in str(exc.value)


def test_plain_value_without_placeholder_unchanged() -> None:
    result = _loader()._expand_env_vars({"host": "localhost", "port": 5432})
    assert result == {"host": "localhost", "port": 5432}


def test_expand_env_var_nested_and_list(monkeypatch) -> None:
    monkeypatch.setenv("DB_PASSWORD", "pw")
    monkeypatch.setenv("REDIS_PASSWORD", "rpw")
    payload = {
        "database": {"password": "${DB_PASSWORD}"},
        "hosts": ["a", "${REDIS_PASSWORD}"],
    }
    result = _loader()._expand_env_vars(payload)
    assert result == {
        "database": {"password": "pw"},
        "hosts": ["a", "rpw"],
    }


def test_loader_expands_env_on_file_load(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DB_PASSWORD", "from-env")
    cfg_file = tmp_path / "cognidb.yaml"
    cfg_file.write_text(
        "database:\n  password: ${DB_PASSWORD}\n  host: localhost\n"
    )
    loader = ConfigLoader(config_file=str(cfg_file))
    loader._load_from_file()
    assert loader._config_data["database"]["password"] == "from-env"
    assert loader._config_data["database"]["host"] == "localhost"


def test_loader_file_load_unset_env_raises(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("MISSING_SECRET", raising=False)
    cfg_file = tmp_path / "cognidb.yaml"
    cfg_file.write_text("database:\n  password: ${MISSING_SECRET}\n")
    loader = ConfigLoader(config_file=str(cfg_file))
    with pytest.raises(ConfigurationError) as exc:
        loader._load_from_file()
    assert "MISSING_SECRET" in str(exc.value)


# ---------------------------------------------------------------------------
# Fix 4 — no secret ever reaches the logs
# ---------------------------------------------------------------------------


def test_no_secret_written_to_logs(tmp_path: Path, caplog) -> None:
    secret = "never-log-this-value"
    with caplog.at_level(logging.DEBUG):
        sm = _file_manager(tmp_path / "secrets.enc")
        sm.set_secret("DB_PASSWORD", secret)
        assert sm.get_secret("DB_PASSWORD") == secret

    for record in caplog.records:
        assert secret not in record.getMessage()
