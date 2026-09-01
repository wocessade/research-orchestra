from __future__ import annotations

import pytest

from bogda_console.config import Settings, assert_public_host, assert_safe_port
from bogda_console.constants import (
    DEFAULT_DEEPSEEK_API_BASE,
    PI_SERVICE_POOL,
    RESEARCH_POOL,
)


def test_default_mock_profile_uses_3101_and_loopback_3102() -> None:
    settings = Settings.from_env({})
    assert settings.profile == "mock-all"
    assert settings.public_host == "127.0.0.1"
    assert settings.public_port == 3101
    assert settings.bff_host == "127.0.0.1"
    assert settings.bff_port == 3102


@pytest.mark.parametrize("purpose", ["public", "bff", "test"])
def test_every_new_console_entry_point_rejects_3100(purpose: str) -> None:
    with pytest.raises(ValueError, match="3100 is reserved"):
        assert_safe_port(3100, purpose)


def test_public_host_allows_loopback_and_rk3528_tailnet() -> None:
    assert assert_public_host("127.0.0.1", {}) == "127.0.0.1"
    assert Settings.from_env(
        {"BOGDA_CONSOLE_PUBLIC_HOST": "100.78.158.80"}
    ).public_host == "100.78.158.80"


def test_public_host_allowlist_can_be_extended_by_env() -> None:
    env = {"BOGDA_CONSOLE_SAFE_PUBLIC_HOSTS": "127.0.0.1,100.64.1.8"}
    assert assert_public_host("100.64.1.8", env) == "100.64.1.8"
    with pytest.raises(ValueError, match="100.64.1.8"):
        assert_public_host("100.78.158.80", env)


def test_public_host_allowlist_always_keeps_loopback() -> None:
    env = {"BOGDA_CONSOLE_SAFE_PUBLIC_HOSTS": "100.64.1.8"}
    assert assert_public_host("127.0.0.1", env) == "127.0.0.1"


def test_public_host_rejects_wildcard_bind_without_opt_in() -> None:
    with pytest.raises(ValueError, match="BOGDA_CONSOLE_PUBLIC_HOST"):
        Settings.from_env({"BOGDA_CONSOLE_PUBLIC_HOST": "0.0.0.0"})


def test_public_host_wildcard_requires_explicit_opt_in() -> None:
    settings = Settings.from_env(
        {
            "BOGDA_CONSOLE_PUBLIC_HOST": "0.0.0.0",
            "BOGDA_CONSOLE_ALLOW_UNSAFE_BIND": "1",
        }
    )
    assert settings.public_host == "0.0.0.0"


def test_unsupported_profile_fails_closed() -> None:
    with pytest.raises(ValueError, match="Unsupported BOGDA_CONSOLE_PROFILE"):
        Settings.from_env({"BOGDA_CONSOLE_PROFILE": "real-prefect-mock-results"})


def test_exact_allowlists_are_parsed_without_wildcards() -> None:
    settings = Settings.from_env(
        {
            "BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS": "dep-a, dep-b",
            "BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS": "schedule-a",
            "BOGDA_CONSOLE_ALLOWED_QUEUE_IDS": "queue-a",
            "BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES": "dorm-x86",
        }
    )
    assert settings.allowed_deployment_ids == frozenset({"dep-a", "dep-b"})
    assert settings.allowed_schedule_ids == frozenset({"schedule-a"})
    assert settings.allowed_queue_ids == frozenset({"queue-a"})
    assert settings.allowed_work_pool_names == frozenset({"dorm-x86"})


@pytest.mark.parametrize(
    "key",
    [
        "BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS",
        "BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS",
        "BOGDA_CONSOLE_ALLOWED_QUEUE_IDS",
        "BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES",
    ],
)
@pytest.mark.parametrize("value", ["*", "pi-service,*"])
def test_allowlist_wildcards_fail_closed(key: str, value: str) -> None:
    with pytest.raises(ValueError, match="wildcards"):
        Settings.from_env({key: value})


def test_real_readonly_disables_all_commands() -> None:
    settings = Settings.from_env({"BOGDA_CONSOLE_PROFILE": "real-readonly"})
    assert settings.commands_enabled is False
    assert settings.review_enabled is False


def test_prefect_auth_string_is_preserved_for_server_side_client() -> None:
    settings = Settings.from_env({"PREFECT_API_AUTH_STRING": "auth-sentinel"})
    assert settings.prefect_api_auth_string == "auth-sentinel"


def test_allowlisted_test_requires_exactly_one_replica() -> None:
    with pytest.raises(ValueError, match="allowlisted-test requires exactly one replica"):
        Settings.from_env(
            {"BOGDA_CONSOLE_PROFILE": "allowlisted-test", "BOGDA_CONSOLE_REPLICA_COUNT": "2"}
        )


def test_default_roles_follow_profile() -> None:
    assert Settings.from_env({}).role == "owner"
    assert Settings.from_env({"BOGDA_CONSOLE_PROFILE": "real-readonly"}).role == "observer"
    assert Settings.from_env({"BOGDA_CONSOLE_PROFILE": "allowlisted-test"}).role == "owner"
    assert Settings.from_env({}).actor_id == "local-owner"


def test_unsupported_role_fails_closed() -> None:
    with pytest.raises(ValueError, match="Unsupported BOGDA_CONSOLE_ROLE"):
        Settings.from_env({"BOGDA_CONSOLE_ROLE": "admin"})


def test_observer_cannot_enable_commands_even_on_allowlisted_test() -> None:
    settings = Settings.from_env(
        {
            "BOGDA_CONSOLE_PROFILE": "allowlisted-test",
            "BOGDA_CONSOLE_ROLE": "observer",
            "BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS": "deployment-dorm",
        }
    )
    assert settings.commands_enabled is False
    assert settings.review_enabled is False
    assert settings.model_control_enabled is False
    assert settings.autonomy_writes_enabled is False


def test_operator_may_run_prefect_commands_but_not_model_control() -> None:
    settings = Settings.from_env(
        {
            "BOGDA_CONSOLE_PROFILE": "allowlisted-test",
            "BOGDA_CONSOLE_ROLE": "operator",
        }
    )
    assert settings.commands_enabled is True
    assert settings.model_control_enabled is False
    assert settings.autonomy_writes_enabled is False


def test_recovery_writes_require_owner_and_usage_unknown_db() -> None:
    bare = Settings.from_env({"BOGDA_CONSOLE_PROFILE": "allowlisted-test"})
    assert bare.recovery_writes_enabled is False
    wired = Settings.from_env(
        {
            "BOGDA_CONSOLE_PROFILE": "allowlisted-test",
            "BOGDA_USAGE_UNKNOWN_DB": "C:/tmp/recovery.sqlite",
        }
    )
    assert wired.recovery_writes_enabled is True
    observer = Settings.from_env(
        {
            "BOGDA_CONSOLE_PROFILE": "allowlisted-test",
            "BOGDA_CONSOLE_ROLE": "observer",
            "BOGDA_USAGE_UNKNOWN_DB": "C:/tmp/recovery.sqlite",
        }
    )
    assert observer.recovery_writes_enabled is False


HMAC32 = "ab" * 32


def test_approval_writes_require_owner_db_and_hmac_key() -> None:
    bare = Settings.from_env({"BOGDA_CONSOLE_PROFILE": "allowlisted-test"})
    assert bare.approval_writes_enabled is False
    wired = Settings.from_env(
        {
            "BOGDA_CONSOLE_PROFILE": "allowlisted-test",
            "BOGDA_APPROVAL_DB": "C:/tmp/approval.sqlite",
            "BOGDA_APPROVAL_HMAC_KEY": HMAC32,
        }
    )
    assert wired.approval_writes_enabled is True
    assert wired.approval_hmac_key == bytes.fromhex(HMAC32)
    observer = Settings.from_env(
        {
            "BOGDA_CONSOLE_PROFILE": "allowlisted-test",
            "BOGDA_CONSOLE_ROLE": "observer",
            "BOGDA_APPROVAL_DB": "C:/tmp/approval.sqlite",
            "BOGDA_APPROVAL_HMAC_KEY": HMAC32,
        }
    )
    assert observer.approval_writes_enabled is False


def test_approval_db_and_hmac_must_be_paired() -> None:
    with pytest.raises(ValueError, match="BOGDA_APPROVAL"):
        Settings.from_env({"BOGDA_APPROVAL_DB": "C:/tmp/approval.sqlite"})
    with pytest.raises(ValueError, match="BOGDA_APPROVAL"):
        Settings.from_env({"BOGDA_APPROVAL_HMAC_KEY": HMAC32})


def test_approval_hmac_key_must_be_32_byte_hex() -> None:
    with pytest.raises(ValueError, match="hex"):
        Settings.from_env(
            {
                "BOGDA_APPROVAL_DB": "C:/tmp/approval.sqlite",
                "BOGDA_APPROVAL_HMAC_KEY": "not-hex",
            }
        )
    with pytest.raises(ValueError, match="32"):
        Settings.from_env(
            {
                "BOGDA_APPROVAL_DB": "C:/tmp/approval.sqlite",
                "BOGDA_APPROVAL_HMAC_KEY": "ab" * 16,
            }
        )


def test_artifact_cleanup_requires_owner_and_artifact_root() -> None:
    bare = Settings.from_env({"BOGDA_CONSOLE_PROFILE": "allowlisted-test"})
    assert bare.artifact_cleanup_enabled is False
    wired = Settings.from_env(
        {
            "BOGDA_CONSOLE_PROFILE": "allowlisted-test",
            "BOGDA_ARTIFACT_ROOT": "C:/tmp/artifacts",
        }
    )
    assert wired.artifact_cleanup_enabled is True
    observer = Settings.from_env(
        {
            "BOGDA_CONSOLE_PROFILE": "allowlisted-test",
            "BOGDA_CONSOLE_ROLE": "observer",
            "BOGDA_ARTIFACT_ROOT": "C:/tmp/artifacts",
        }
    )
    assert observer.artifact_cleanup_enabled is False


def test_console_named_defaults_stay_aligned_with_bogda() -> None:
    from bogda.budget.deepseek_balance import DEFAULT_DEEPSEEK_API_BASE as bogda_base
    from bogda.contracts.runner_packet import PI_SERVICE_POOL as bogda_pi
    from bogda.contracts.runner_packet import RESEARCH_POOL as bogda_research

    assert DEFAULT_DEEPSEEK_API_BASE == bogda_base
    assert PI_SERVICE_POOL == bogda_pi
    assert RESEARCH_POOL == bogda_research
    assert Settings.from_env({}).deepseek_api_base == DEFAULT_DEEPSEEK_API_BASE

