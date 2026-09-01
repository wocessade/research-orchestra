from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from bogda_console.constants import DEFAULT_DEEPSEEK_API_BASE


SAFE_PROFILES = frozenset({"mock-all", "real-readonly", "allowlisted-test"})

# Loopback plus the current RK3528 tailnet address. Override with
# BOGDA_CONSOLE_SAFE_PUBLIC_HOSTS. 0.0.0.0 needs an explicit opt-in.
DEFAULT_SAFE_PUBLIC_HOSTS = ("127.0.0.1", "100.78.158.80")
SAFE_PUBLIC_HOSTS = frozenset(DEFAULT_SAFE_PUBLIC_HOSTS)


def safe_public_hosts(env: Mapping[str, str]) -> frozenset[str]:
    raw = env.get("BOGDA_CONSOLE_SAFE_PUBLIC_HOSTS")
    if raw is None or raw.strip() == "":
        hosts = set(DEFAULT_SAFE_PUBLIC_HOSTS)
    else:
        hosts = {part.strip() for part in raw.split(",") if part.strip()}
    hosts.add("127.0.0.1")
    if "*" in hosts:
        raise ValueError("wildcards are not allowed in BOGDA_CONSOLE_SAFE_PUBLIC_HOSTS")
    if any(host in {"0.0.0.0", "::"} for host in hosts):
        raise ValueError(
            "wildcard bind addresses cannot be listed in BOGDA_CONSOLE_SAFE_PUBLIC_HOSTS"
        )
    return frozenset(hosts)


class ConsoleRole(StrEnum):
    OWNER = "owner"
    OBSERVER = "observer"
    OPERATOR = "operator"


_DEFAULT_ROLE = {
    "mock-all": ConsoleRole.OWNER,
    "real-readonly": ConsoleRole.OBSERVER,
    "allowlisted-test": ConsoleRole.OWNER,
}


def assert_safe_port(port: int, purpose: str) -> int:
    if port == 3100:
        raise ValueError(f"3100 is reserved for the legacy console ({purpose})")
    if not 1 <= port <= 65535:
        raise ValueError(f"invalid {purpose} port: {port}")
    return port


def assert_public_host(host: str, env: Mapping[str, str]) -> str:
    allowed = safe_public_hosts(env)
    if host in allowed:
        return host
    if host in {"0.0.0.0", "::"} and env.get("BOGDA_CONSOLE_ALLOW_UNSAFE_BIND") == "1":
        return host
    allowed_text = ", ".join(sorted(allowed))
    raise ValueError(
        f"BOGDA_CONSOLE_PUBLIC_HOST must be one of {allowed_text} "
        "(set BOGDA_CONSOLE_ALLOW_UNSAFE_BIND=1 only for a reviewed bind)"
    )


def _exact_set(value: str | None) -> frozenset[str]:
    values = frozenset(part.strip() for part in (value or "").split(",") if part.strip())
    if "*" in values:
        raise ValueError("wildcards are not allowed in command allowlists")
    return values


def _parse_hmac_key(value: str | None) -> bytes | None:
    if value is None or value == "":
        return None
    try:
        key = bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError("BOGDA_APPROVAL_HMAC_KEY must be hex") from exc
    if len(key) < 32:
        raise ValueError("BOGDA_APPROVAL_HMAC_KEY must be at least 32 bytes")
    return key


@dataclass(frozen=True, slots=True)
class Settings:
    profile: str
    public_host: str
    public_port: int
    bff_host: str
    bff_port: int
    fixture_scenario: str
    test_mode: bool
    prefect_api_url: str | None
    prefect_api_auth_string: str | None
    prefect_api_key: str | None
    deepseek_api_key: str | None
    deepseek_api_base: str
    replica_count: int
    allowed_deployment_ids: frozenset[str]
    allowed_schedule_ids: frozenset[str]
    allowed_queue_ids: frozenset[str]
    allowed_work_pool_names: frozenset[str]
    actor_id: str
    role: ConsoleRole
    artifact_root: str | None
    usage_unknown_db: str | None
    approval_db: str | None
    approval_hmac_key: bytes | None

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        profile = env.get("BOGDA_CONSOLE_PROFILE", "mock-all")
        if profile not in SAFE_PROFILES:
            raise ValueError(f"Unsupported BOGDA_CONSOLE_PROFILE: {profile}")
        public_port = assert_safe_port(
            int(env.get("BOGDA_CONSOLE_PUBLIC_PORT", "3101")), "public"
        )
        bff_port = assert_safe_port(int(env.get("BOGDA_CONSOLE_BFF_PORT", "3102")), "bff")
        replica_count = int(env.get("BOGDA_CONSOLE_REPLICA_COUNT", "1"))
        if replica_count < 1:
            raise ValueError("BOGDA_CONSOLE_REPLICA_COUNT must be at least 1")
        if profile == "allowlisted-test" and replica_count != 1:
            raise ValueError("allowlisted-test requires exactly one replica")
        role_value = env.get("BOGDA_CONSOLE_ROLE")
        if role_value is None or role_value == "":
            role = _DEFAULT_ROLE[profile]
        else:
            try:
                role = ConsoleRole(role_value)
            except ValueError as exc:
                raise ValueError(f"Unsupported BOGDA_CONSOLE_ROLE: {role_value}") from exc
        actor_id = env.get("BOGDA_CONSOLE_ACTOR", "local-owner").strip()
        if not actor_id:
            raise ValueError("BOGDA_CONSOLE_ACTOR must be a non-empty string")
        approval_db = env.get("BOGDA_APPROVAL_DB") or None
        approval_hmac_key = _parse_hmac_key(env.get("BOGDA_APPROVAL_HMAC_KEY"))
        if bool(approval_db) != bool(approval_hmac_key):
            raise ValueError("BOGDA_APPROVAL_DB and BOGDA_APPROVAL_HMAC_KEY must be set together")
        public_host = assert_public_host(
            env.get("BOGDA_CONSOLE_PUBLIC_HOST", "127.0.0.1"), env
        )
        return cls(
            profile=profile,
            public_host=public_host,
            public_port=public_port,
            bff_host="127.0.0.1",
            bff_port=bff_port,
            fixture_scenario=env.get("BOGDA_CONSOLE_FIXTURE", "normal-active"),
            test_mode=env.get("BOGDA_CONSOLE_TEST_MODE", "0") == "1",
            prefect_api_url=env.get("PREFECT_API_URL"),
            prefect_api_auth_string=env.get("PREFECT_API_AUTH_STRING"),
            prefect_api_key=env.get("PREFECT_API_KEY"),
            deepseek_api_key=env.get("DEEPSEEK_API_KEY"),
            deepseek_api_base=env.get("DEEPSEEK_API_BASE", DEFAULT_DEEPSEEK_API_BASE),
            replica_count=replica_count,
            allowed_deployment_ids=_exact_set(
                env.get("BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS")
            ),
            allowed_schedule_ids=_exact_set(env.get("BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS")),
            allowed_queue_ids=_exact_set(env.get("BOGDA_CONSOLE_ALLOWED_QUEUE_IDS")),
            allowed_work_pool_names=_exact_set(
                env.get("BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES")
            ),
            actor_id=actor_id,
            role=role,
            artifact_root=env.get("BOGDA_ARTIFACT_ROOT") or None,
            usage_unknown_db=env.get("BOGDA_USAGE_UNKNOWN_DB") or None,
            approval_db=approval_db,
            approval_hmac_key=approval_hmac_key,
        )

    @property
    def commands_enabled(self) -> bool:
        if self.role is ConsoleRole.OBSERVER:
            return False
        return self.profile in {"mock-all", "allowlisted-test"}

    @property
    def review_enabled(self) -> bool:
        return self.commands_enabled and self.replica_count == 1

    @property
    def autonomy_writes_enabled(self) -> bool:
        return self.profile == "mock-all" and self.role is ConsoleRole.OWNER

    @property
    def model_control_enabled(self) -> bool:
        return self.profile == "mock-all" and self.role is ConsoleRole.OWNER

    @property
    def recovery_writes_enabled(self) -> bool:
        return (
            self.role is ConsoleRole.OWNER
            and self.profile in {"mock-all", "allowlisted-test"}
            and bool(self.usage_unknown_db)
        )

    @property
    def approval_writes_enabled(self) -> bool:
        return (
            self.role is ConsoleRole.OWNER
            and self.profile in {"mock-all", "allowlisted-test"}
            and bool(self.approval_db)
            and bool(self.approval_hmac_key)
        )

    @property
    def artifact_cleanup_enabled(self) -> bool:
        return (
            self.role is ConsoleRole.OWNER
            and self.profile in {"mock-all", "allowlisted-test"}
            and bool(self.artifact_root)
        )

