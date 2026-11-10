"""
Deterministic Negative Authorization Verification Suite
Verifies that destructive test execution is rejected fail-closed specifically
due to missing explicit opt-in (ALLOW_TEST_DB_RESET), and confirms that:
1. The failure is an exact PermissionError regarding missing authorization.
2. Unrelated failures (imports, syntax, connection issues, assertion errors) fail the check.
3. No destructive tests or DDL operations are executed against the database.
"""
import os
import sys
import subprocess
from pathlib import Path
import pytest
from sqlalchemy import create_engine, MetaData
from app.core.config import settings
from app.core.db_safety import (
    REGULAR_TEST_PURPOSE,
    REGULAR_TEST_OPT_IN_VARS,
    TEST_RUNTIME_ROLE,
    verify_database_isolation,
    validate_database_target,
    safe_drop_all,
    safe_create_all,
)

TEST_DB_PASSWORD = os.getenv("TEST_DB_PASSWORD", "test_secure_password")
TEST_DATABASE_URL = f"postgresql://{TEST_RUNTIME_ROLE}:{TEST_DB_PASSWORD}@localhost:5432/scheme_saathi_test"


def test_runner_rejects_destructive_execution_without_opt_in():
    """
    Executes pytest against test_database.py without ALLOW_TEST_DB_RESET.
    Confirms:
    - Exit code is nonzero.
    - Failure is specifically PermissionError: explicit opt-in required.
    - Zero tests passed (destructive test functions were never executed).
    - Failure was not caused by unrelated issues (ImportError, OperationalError, etc.).
    - Every collected test failed at fixture setup rather than executing.
    """
    backend_dir = Path(__file__).resolve().parent.parent.parent
    env = os.environ.copy()
    
    # Explicitly ensure all regular test opt-in variables are completely absent
    for var in REGULAR_TEST_OPT_IN_VARS:
        env.pop(var, None)
    
    env["PYTHONPATH"] = str(backend_dir)
    env["TEST_DB_PASSWORD"] = TEST_DB_PASSWORD
    env["DATABASE_URL"] = settings.DATABASE_URL
    # Ensure Testcontainers is not forcing dynamic opt-in bypass
    env.pop("USE_TESTCONTAINERS", None)

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/integration/test_database.py",
        "-v",
    ]

    result = subprocess.run(
        cmd,
        cwd=str(backend_dir),
        env=env,
        capture_output=True,
        text=True,
    )

    combined_output = result.stdout + "\n" + result.stderr

    # 1. Must exit with failure
    assert result.returncode != 0, "Test runner unexpectedly succeeded without explicit opt-in!"

    # 2. Must specifically fail with PermissionError and explicit opt-in requirement
    assert "PermissionError" in combined_output, (
        f"Expected PermissionError but got different error. Output:\n{combined_output}"
    )
    assert "Destructive operation on regular test database rejected: explicit opt-in required" in combined_output, (
        f"Expected exact rejection message in output. Output:\n{combined_output}"
    )
    assert "ALLOW_TEST_DB_RESET" in combined_output, (
        f"Expected 'ALLOW_TEST_DB_RESET' in output. Output:\n{combined_output}"
    )

    # 3. Must NOT be an unrelated failure
    unrelated_errors = [
        "ImportError",
        "ModuleNotFoundError",
        "OperationalError",
        "ConnectionRefusedError",
        "could not connect to server",
        "SyntaxError",
        "AttributeError",
        "NameError",
        "IndentationError",
    ]
    for err in unrelated_errors:
        assert err not in combined_output, (
            f"Test failed due to unrelated error '{err}' rather than authorization check!\n{combined_output}"
        )

    # 4. Confirms destructive tests did not execute
    assert "PASSED" not in combined_output, (
        f"Destructive tests executed and passed when they should have been blocked!\n{combined_output}"
    )
    assert "FAILED" not in combined_output, (
        f"Tests reached execution phase and failed, rather than aborting at setup fixture!\n{combined_output}"
    )
    assert "ERROR at setup of test_create_user_and_profile_relationship" in combined_output
    assert "ERROR at setup of test_duplicate_email_constraint" in combined_output
    assert "ERROR at setup of test_user_consent_recording" in combined_output
    assert "ERROR at setup of test_consent_retention_foreign_key_protection" in combined_output
    assert "4 errors" in combined_output


def test_fixture_setup_raises_exact_permission_error_without_opt_in(monkeypatch):
    """
    Direct in-process assertion:
    Verifies that calling verify_database_isolation and validate_database_target
    without opt-in raises PermissionError specifically.
    """
    for var in REGULAR_TEST_OPT_IN_VARS:
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(PermissionError) as exc_info:
        verify_database_isolation(
            target_url=TEST_DATABASE_URL,
            app_url=settings.DATABASE_URL,
            expected_purpose=REGULAR_TEST_PURPOSE,
            enforce_opt_in=True,
            expected_role=TEST_RUNTIME_ROLE,
        )
    assert "explicit opt-in required" in str(exc_info.value)
    assert "ALLOW_TEST_DB_RESET" in str(exc_info.value)

    with pytest.raises(PermissionError) as exc_info2:
        validate_database_target(
            target_url=TEST_DATABASE_URL,
            app_url=settings.DATABASE_URL,
            target_label="regular test database",
            enforce_opt_in=True,
            expected_role=TEST_RUNTIME_ROLE,
        )
    assert "explicit opt-in required" in str(exc_info2.value)


def test_gateways_raise_exact_permission_error_without_opt_in(monkeypatch):
    """
    Direct in-process assertion:
    Verifies that calling safe_drop_all and safe_create_all without opt-in
    raises PermissionError specifically.
    """
    for var in REGULAR_TEST_OPT_IN_VARS:
        monkeypatch.delenv(var, raising=False)

    engine = create_engine(TEST_DATABASE_URL)
    meta = MetaData()
    try:
        with pytest.raises(PermissionError) as exc_info:
            safe_drop_all(
                engine,
                meta,
                TEST_DATABASE_URL,
                settings.DATABASE_URL,
                purpose=REGULAR_TEST_PURPOSE,
                expected_role=TEST_RUNTIME_ROLE,
            )
        assert "explicit opt-in required" in str(exc_info.value)

        with pytest.raises(PermissionError) as exc_info2:
            safe_create_all(
                engine,
                meta,
                TEST_DATABASE_URL,
                settings.DATABASE_URL,
                purpose=REGULAR_TEST_PURPOSE,
                expected_role=TEST_RUNTIME_ROLE,
            )
        assert "explicit opt-in required" in str(exc_info2.value)
    finally:
        engine.dispose()


def test_api_runner_rejects_destructive_execution_without_opt_in():
    """
    Executes pytest against test_profile.py without ALLOW_TEST_DB_RESET.
    Confirms:
    - Exit code is nonzero.
    - Failure is specifically PermissionError: explicit opt-in required.
    - Zero tests passed.
    """
    backend_dir = Path(__file__).resolve().parent.parent.parent
    env = os.environ.copy()
    
    for var in REGULAR_TEST_OPT_IN_VARS:
        env.pop(var, None)
    
    env["PYTHONPATH"] = str(backend_dir)
    env["TEST_DB_PASSWORD"] = TEST_DB_PASSWORD
    env["DATABASE_URL"] = settings.DATABASE_URL
    env.pop("USE_TESTCONTAINERS", None)

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/api/test_profile.py",
        "-k",
        "test_get_own_profile",
        "-v",
    ]

    result = subprocess.run(
        cmd,
        cwd=str(backend_dir),
        env=env,
        capture_output=True,
        text=True,
    )

    combined_output = result.stdout + "\n" + result.stderr

    assert result.returncode != 0, "API test unexpectedly succeeded without opt-in!"
    assert "PermissionError" in combined_output
    assert "explicit opt-in required" in combined_output
    assert "PASSED" not in combined_output
