from __future__ import annotations

import base64
import importlib.util
import os
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[1] / "deploy/runtime-secrets"


def load_script(filename):
    spec = importlib.util.spec_from_file_location(filename, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    checker = load_script("check-runtime-secrets.py")
    directory = tmp_path / "secrets"
    directory.mkdir(mode=0o700)
    for setting, filename in checker.SECRET_FILES.items():
        value = (
            "synthetic-value"
            if setting
            in {
                "SECRET_KEY",
                "POSTGRES_PASSWORD",
                "REDIS_PASSWORD",
                "S3_ACCESS_KEY_ID",
                "S3_SECRET_ACCESS_KEY",
                "AUTH_TOTP_ENCRYPTION_KEY",
                "ROUTINE_INTERVIEW_ENCRYPTION_KEYS",
                "COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS",
                "REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
                "EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
                "INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
                "GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
                "ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
                "FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
            }
            else ""
        )
        if setting == "COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS":
            value = base64.urlsafe_b64encode(b"s" * 32).decode("ascii")
        path = directory / filename
        path.write_text(value)
        path.chmod(0o444)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "APP_ENV=live-staging\n"
        + "\n".join(
            f"{setting}_FILE=/run/secrets/{filename}"
            for setting, filename in checker.SECRET_FILES.items()
        )
        + "\n"
    )
    return checker, directory, env_file


def verify(runtime):
    checker, directory, env_file = runtime
    checker.check_runtime(directory, env_file, os.getuid())


def test_valid_file_only_configuration_with_optional_empty_files(runtime, monkeypatch):
    original = Path.read_text

    def guard(path, *args, **kwargs):
        assert path.parent != runtime[1], "preflight must never read secret contents"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guard)
    verify(runtime)


@pytest.mark.parametrize("fault", ["missing", "symlink", "mode", "owner"])
def test_directory_metadata(runtime, fault):
    checker, directory, env_file = runtime
    owner = os.getuid()
    if fault == "missing":
        directory = directory / "missing"
    elif fault == "symlink":
        link = directory.parent / "linked"
        link.symlink_to(directory, target_is_directory=True)
        directory = link
    elif fault == "mode":
        directory.chmod(0o755)
    else:
        owner += 1
    with pytest.raises(ValueError, match="secret directory"):
        checker.check_runtime(directory, env_file, owner)


@pytest.mark.parametrize("fault", ["missing", "empty", "symlink", "mode", "directory"])
def test_file_metadata(runtime, fault):
    path = runtime[1] / "django_secret_key"
    if fault in {"missing", "symlink", "directory"}:
        path.unlink()
        if fault == "symlink":
            path.symlink_to(runtime[1] / "postgres_password")
        elif fault == "directory":
            path.mkdir()
    elif fault == "empty":
        path.chmod(0o600)
        path.write_text("")
        path.chmod(0o444)
    else:
        path.chmod(0o600)
    with pytest.raises(ValueError, match="django_secret_key"):
        verify(runtime)


@pytest.mark.parametrize(
    "name",
    [
        "SECRET_KEY",
        "SMTP_PASSWORD",
        "COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS",
        "REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
        "EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
        "INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
        "GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
        "ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
        "FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
        "REDIS_URL",
        "CELERY_BROKER_URL",
        "REDIS_CACHE_URL_FILE",
        "DEMO_ACCOUNT_PASSWORD",
        "DEMO_ACCOUNT_PASSWORD_FILE",
    ],
)
def test_forbidden_assignments_never_expose_values(runtime, name):
    with runtime[2].open("a") as output:
        output.write(f"{name}=password-sentinel\n")
    with pytest.raises(ValueError) as error:
        verify(runtime)
    assert name in str(error.value)
    assert "password-sentinel" not in str(error.value)


@pytest.mark.parametrize("pointer", ["", "/wrong/path", '"/wrong/path"', "${UNTRUSTED_PATH}"])
def test_missing_or_wrong_pointer(runtime, pointer):
    content = runtime[2].read_text().splitlines()
    content = [line for line in content if not line.startswith("SECRET_KEY_FILE=")]
    if pointer:
        content.append(f"SECRET_KEY_FILE={pointer}")
    runtime[2].write_text("\n".join(content))
    with pytest.raises(ValueError, match="SECRET_KEY_FILE"):
        verify(runtime)


def test_quoted_pointer_and_comments(runtime):
    content = (
        runtime[2]
        .read_text()
        .replace(
            "SECRET_KEY_FILE=/run/secrets/django_secret_key",
            "export SECRET_KEY_FILE='/run/secrets/django_secret_key' # pointer only",
        )
    )
    runtime[2].write_text(content)
    verify(runtime)


def test_duplicate_assignments_fail_without_echoing_line(runtime):
    with runtime[2].open("a") as output:
        output.write("APP_ENV=password-sentinel\n")
    with pytest.raises(ValueError) as error:
        verify(runtime)
    assert "duplicate" in str(error.value)
    assert "password-sentinel" not in str(error.value)


def test_source_directory_must_match_compose_configuration(runtime):
    with runtime[2].open("a") as output:
        output.write("COMPASS_SECRETS_DIR=/wrong/directory\n")
    with pytest.raises(ValueError, match="COMPASS_SECRETS_DIR"):
        verify(runtime)


@pytest.fixture
def migration(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    module = load_script("migrate-runtime-secrets.py")
    directory = tmp_path / "secrets"
    directory.mkdir(mode=0o700)
    for setting in module.SECRET_FILES:
        monkeypatch.delenv(f"{setting}_FILE", raising=False)
        monkeypatch.setenv(setting, f'synthetic-{setting} @:/#% " \\ 雪')
    monkeypatch.setenv("SMTP_PASSWORD", "")
    monkeypatch.setenv("ROUTINE_INTERVIEW_ENCRYPTION_KEYS", "first-key,second-key")
    return module, directory


def test_export_and_compare_preserve_exact_values_and_key_order(migration):
    module, directory = migration
    values = module.effective_values()
    module.export_values(directory, values)
    assert module.compare_values(directory, values)
    assert (directory / "routine_interview_encryption_keys").read_bytes() == b"first-key,second-key"
    for filename in module.SECRET_FILES.values():
        assert (directory / filename).stat().st_mode & 0o777 == 0o444
    assert (directory / "smtp_password").read_bytes() == b""
    assert not list(directory.glob(".provision-*"))


def test_export_from_existing_file_contract(migration, monkeypatch, tmp_path):
    module, directory = migration
    source = tmp_path / "existing-keyring"
    source.write_bytes(b"first-key,second-key\r\n")
    monkeypatch.delenv("ROUTINE_INTERVIEW_ENCRYPTION_KEYS")
    monkeypatch.setenv("ROUTINE_INTERVIEW_ENCRYPTION_KEYS_FILE", str(source))
    module.export_values(directory, module.effective_values())
    assert (directory / "routine_interview_encryption_keys").read_bytes() == b"first-key,second-key"


def test_export_refuses_to_overwrite_any_existing_file(migration):
    module, directory = migration
    target = directory / "smtp_password"
    target.write_text("original-value")
    with pytest.raises(ValueError, match="refusing to overwrite"):
        module.export_values(directory, module.effective_values())
    assert target.read_text() == "original-value"
    assert not (directory / "django_secret_key").exists()


def test_compare_reports_only_mismatched_setting(migration, capsys):
    module, directory = migration
    values = module.effective_values()
    module.export_values(directory, values)
    values["SECRET_KEY"] = b"different-password-sentinel"
    assert not module.compare_values(directory, values)
    assert capsys.readouterr().err == "SECRET_KEY: mismatch\n"


@pytest.mark.parametrize(
    "value", ["", "password-sentinel\rtext", "password-sentinel\n", "password-sentinel\x00"]
)
def test_missing_or_unrepresentable_effective_values_fail_before_export(
    migration, monkeypatch, value
):
    module, directory = migration
    if "\x00" in value:
        source = directory.parent / "source"
        source.write_text(value)
        monkeypatch.delenv("SECRET_KEY")
        monkeypatch.setenv("SECRET_KEY_FILE", str(source))
    else:
        monkeypatch.setenv("SECRET_KEY", value)
    with pytest.raises(ValueError) as error:
        module.effective_values()
    assert "password-sentinel" not in str(error.value)
    assert not list(directory.iterdir())


@pytest.mark.parametrize("fault", ["empty", "missing", "wrong-pointer", "direct"])
def test_new_summary_secret_required_and_pointer_only(runtime, fault):
    checker, directory, env_file = runtime
    assert len(checker.SECRET_FILES) == 22
    setting = "COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS"
    filename = "counseling_shared_summary_encryption_keys"
    assert checker.SECRET_FILES[setting] == filename
    path = directory / filename
    if fault == "empty":
        path.chmod(0o600)
        path.write_text("")
        path.chmod(0o444)
    elif fault == "missing":
        path.unlink()
    elif fault == "wrong-pointer":
        env_file.write_text(
            env_file.read_text().replace(
                f"{setting}_FILE=/run/secrets/{filename}", f"{setting}_FILE=/wrong/path"
            )
        )
    else:
        with env_file.open("a") as output:
            output.write(f"{setting}=private-sentinel\n")
    with pytest.raises(ValueError) as caught:
        verify(runtime)
    assert "private-sentinel" not in str(caught.value)
    assert setting in str(caught.value) or filename in str(caught.value)


def test_export_cannot_generate_absent_new_summary_key(migration, monkeypatch):
    module, directory = migration
    monkeypatch.delenv("COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS")
    with pytest.raises(ValueError, match="COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS"):
        module.effective_values()
    assert not list(directory.iterdir())


@pytest.mark.parametrize("fault", ["empty", "missing", "wrong-pointer", "direct"])
def test_new_referral_secret_required_and_pointer_only(runtime, fault):
    checker, directory, env_file = runtime
    assert len(checker.SECRET_FILES) == 22
    setting = "REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"
    filename = "referral_confidential_content_encryption_keys"
    assert checker.SECRET_FILES[setting] == filename
    path = directory / filename
    if fault == "empty":
        path.chmod(0o600)
        path.write_text("")
        path.chmod(0o444)
    elif fault == "missing":
        path.unlink()
    elif fault == "wrong-pointer":
        env_file.write_text(
            env_file.read_text().replace(
                f"{setting}_FILE=/run/secrets/{filename}", f"{setting}_FILE=/wrong/path"
            )
        )
    else:
        with env_file.open("a") as output:
            output.write(f"{setting}=private-sentinel\n")
    with pytest.raises(ValueError) as caught:
        verify(runtime)
    assert "private-sentinel" not in str(caught.value)
    assert setting in str(caught.value) or filename in str(caught.value)


def test_export_cannot_generate_absent_new_referral_key(migration, monkeypatch):
    module, directory = migration
    monkeypatch.delenv("REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS")
    with pytest.raises(ValueError, match="REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"):
        module.effective_values()
    assert not list(directory.iterdir())


@pytest.mark.parametrize("fault", ["empty", "missing", "wrong-pointer", "direct"])
def test_new_exit_interview_secret_required_and_pointer_only(runtime, fault):
    checker, directory, env_file = runtime
    assert len(checker.SECRET_FILES) == 22
    setting = "EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"
    filename = "exit_interview_confidential_content_encryption_keys"
    assert checker.SECRET_FILES[setting] == filename
    path = directory / filename
    if fault == "empty":
        path.chmod(0o600)
        path.write_text("")
        path.chmod(0o444)
    elif fault == "missing":
        path.unlink()
    elif fault == "wrong-pointer":
        env_file.write_text(
            env_file.read_text().replace(
                f"{setting}_FILE=/run/secrets/{filename}", f"{setting}_FILE=/wrong/path"
            )
        )
    else:
        with env_file.open("a") as output:
            output.write(f"{setting}=private-sentinel\n")
    with pytest.raises(ValueError) as caught:
        verify(runtime)
    assert "private-sentinel" not in str(caught.value)
    assert setting in str(caught.value) or filename in str(caught.value)


def test_export_cannot_generate_absent_new_exit_interview_key(migration, monkeypatch):
    module, directory = migration
    monkeypatch.delenv("EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS")
    with pytest.raises(ValueError, match="EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"):
        module.effective_values()
    assert not list(directory.iterdir())


@pytest.mark.parametrize("fault", ["empty", "missing", "wrong-pointer", "direct"])
def test_new_inventory_secret_required_and_pointer_only(runtime, fault):
    checker, directory, env_file = runtime
    assert len(checker.SECRET_FILES) == 22
    setting = "INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"
    filename = "inventory_confidential_content_encryption_keys"
    assert checker.SECRET_FILES[setting] == filename
    path = directory / filename
    if fault == "empty":
        path.chmod(0o600)
        path.write_text("")
        path.chmod(0o444)
    elif fault == "missing":
        path.unlink()
    elif fault == "wrong-pointer":
        env_file.write_text(
            env_file.read_text().replace(
                f"{setting}_FILE=/run/secrets/{filename}", f"{setting}_FILE=/wrong/path"
            )
        )
    else:
        with env_file.open("a") as output:
            output.write(f"{setting}=private-sentinel\n")
    with pytest.raises(ValueError) as caught:
        verify(runtime)
    assert "private-sentinel" not in str(caught.value)
    assert setting in str(caught.value) or filename in str(caught.value)


def test_export_cannot_generate_absent_new_inventory_key(migration, monkeypatch):
    module, directory = migration
    monkeypatch.delenv("INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS")
    with pytest.raises(ValueError, match="INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"):
        module.effective_values()
    assert not list(directory.iterdir())


@pytest.mark.parametrize("fault", ["empty", "missing", "wrong-pointer", "direct"])
def test_new_graduate_tracer_secret_required_and_pointer_only(runtime, fault):
    checker, directory, env_file = runtime
    assert len(checker.SECRET_FILES) == 22
    setting = "GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"
    filename = "graduate_tracer_confidential_content_encryption_keys"
    assert checker.SECRET_FILES[setting] == filename
    path = directory / filename
    if fault == "empty":
        path.chmod(0o600)
        path.write_text("")
        path.chmod(0o444)
    elif fault == "missing":
        path.unlink()
    elif fault == "wrong-pointer":
        env_file.write_text(
            env_file.read_text().replace(
                f"{setting}_FILE=/run/secrets/{filename}", f"{setting}_FILE=/wrong/path"
            )
        )
    else:
        with env_file.open("a") as output:
            output.write(f"{setting}=private-sentinel\n")
    with pytest.raises(ValueError) as caught:
        verify(runtime)
    assert "private-sentinel" not in str(caught.value)
    assert setting in str(caught.value) or filename in str(caught.value)


def test_export_cannot_generate_absent_new_graduate_tracer_key(migration, monkeypatch):
    module, directory = migration
    monkeypatch.delenv("GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS")
    with pytest.raises(ValueError, match="GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"):
        module.effective_values()
    assert not list(directory.iterdir())


@pytest.mark.parametrize("fault", ["empty", "missing", "wrong-pointer", "direct"])
def test_new_account_profile_secret_required_and_pointer_only(runtime, fault):
    checker, directory, env_file = runtime
    assert len(checker.SECRET_FILES) == 22
    setting = "ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"
    filename = "account_profile_confidential_content_encryption_keys"
    assert checker.SECRET_FILES[setting] == filename
    path = directory / filename
    if fault == "empty":
        path.chmod(0o600)
        path.write_text("")
        path.chmod(0o444)
    elif fault == "missing":
        path.unlink()
    elif fault == "wrong-pointer":
        env_file.write_text(
            env_file.read_text().replace(
                f"{setting}_FILE=/run/secrets/{filename}", f"{setting}_FILE=/wrong/path"
            )
        )
    else:
        with env_file.open("a") as output:
            output.write(f"{setting}=private-sentinel\n")
    with pytest.raises(ValueError) as caught:
        verify(runtime)
    assert "private-sentinel" not in str(caught.value)
    assert setting in str(caught.value) or filename in str(caught.value)


def test_export_cannot_generate_absent_new_account_profile_key(migration, monkeypatch):
    module, directory = migration
    monkeypatch.delenv("ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS")
    with pytest.raises(ValueError, match="ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"):
        module.effective_values()
    assert not list(directory.iterdir())


@pytest.mark.parametrize("fault", ["empty", "missing", "wrong-pointer", "direct"])
def test_new_feedback_secret_required_and_pointer_only(runtime, fault):
    checker, directory, env_file = runtime
    assert len(checker.SECRET_FILES) == 22
    setting = "FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"
    filename = "feedback_confidential_content_encryption_keys"
    assert checker.SECRET_FILES[setting] == filename
    path = directory / filename
    if fault == "empty":
        path.chmod(0o600)
        path.write_text("")
        path.chmod(0o444)
    elif fault == "missing":
        path.unlink()
    elif fault == "wrong-pointer":
        env_file.write_text(
            env_file.read_text().replace(
                f"{setting}_FILE=/run/secrets/{filename}", f"{setting}_FILE=/wrong/path"
            )
        )
    else:
        with env_file.open("a") as output:
            output.write(f"{setting}=private-sentinel\n")
    with pytest.raises(ValueError) as caught:
        verify(runtime)
    assert "private-sentinel" not in str(caught.value)
    assert setting in str(caught.value) or filename in str(caught.value)


def test_export_cannot_generate_absent_new_feedback_key(migration, monkeypatch):
    module, directory = migration
    monkeypatch.delenv("FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS")
    with pytest.raises(ValueError, match="FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"):
        module.effective_values()
    assert not list(directory.iterdir())
