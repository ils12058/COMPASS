import json
import runpy
from pathlib import Path

import pytest

from compass.common.runtime_secrets import RUNTIME_SECRET_FILES

tool = runpy.run_path(str(Path(__file__).parents[1] / "deploy/vault/migrate-runtime-secrets.py"))


def test_export_and_comparison_preserve_every_value(tmp_path, monkeypatch, capsys):
    original = tmp_path / "original"
    rendered = tmp_path / "rendered"
    original.mkdir(mode=0o700)
    rendered.mkdir(mode=0o700)
    for setting, filename in RUNTIME_SECRET_FILES.items():
        assert tool["SECRETS"][setting][2] == filename
        value = f'  synthetic {setting} @:/#%\\"  '
        monkeypatch.setenv(setting, value)
        monkeypatch.delenv(f"{setting}_FILE", raising=False)
        (rendered / filename).write_text(value, encoding="utf-8")
    tool["export_current"](original)
    tool["compare_rendered"](original, rendered)
    assert capsys.readouterr().out == ""
    for _setting, (domain, field, filename) in tool["SECRETS"].items():
        path = original / f"{domain}.json"
        assert path.stat().st_mode & 0o777 == 0o600
        assert json.loads(path.read_text())[field] == (rendered / filename).read_text()
    (rendered / "routine_interview_encryption_keys").write_text("changed-key-order")
    with pytest.raises(ValueError, match="^ROUTINE_INTERVIEW_ENCRYPTION_KEYS migration comparison"):
        tool["compare_rendered"](original, rendered)


@pytest.mark.parametrize("value", ["synthetic\n", "synthetic\rinside"])
def test_export_refuses_a_value_that_file_delivery_would_change(tmp_path, monkeypatch, value):
    monkeypatch.setenv("SECRET_KEY", value)
    monkeypatch.delenv("SECRET_KEY_FILE", raising=False)
    with pytest.raises(ValueError, match="^SECRET_KEY cannot be preserved"):
        tool["export_current"](tmp_path)
    assert not list(tmp_path.iterdir())


def test_host_environment_preflight_blocks_secrets_before_docker(capsys):
    check = runpy.run_path(str(Path(__file__).parents[1] / "deploy/vault/check-runtime-env.py"))
    content = "\n".join(
        f"{name}_FILE=/run/secrets/compass/{filename}"
        for name, filename in RUNTIME_SECRET_FILES.items()
    )
    check["validate_assignments"](content + "\nSMTP_HOST=smtp.example.test")
    for setting in check["forbidden"]:
        with pytest.raises(ValueError) as exc:
            check["validate_assignments"](content + f"\n{setting}=synthetic-do-not-echo")
        assert "synthetic-do-not-echo" not in str(exc.value)
    with pytest.raises(ValueError, match="SECRET_KEY_FILE has duplicate runtime assignments"):
        check["validate_assignments"](content + "\nSECRET_KEY_FILE=duplicate")
    with pytest.raises(ValueError, match="SECRET_KEY_FILE is missing"):
        check["validate_assignments"]("SMTP_HOST=smtp.example.test")
    assert capsys.readouterr().out == ""
