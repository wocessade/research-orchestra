from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


SAFE_PROFILES = frozenset({"mock-all", "real-readonly", "allowlisted-test"})


def assert_safe_port(port: int, purpose: str) -> int:
    if port == 3100:
        raise ValueError(f"3100 is reserved for the legacy console ({purpose})")
    if not 1 <= port <= 65535:
        raise ValueError(f"invalid {purpose} port: {port}")
    return port


def _exact_set(value: str | None) -> frozenset[str]:
    values = frozenset(part.strip() for part in (value or "").split(",") if part.strip())
    if "*" in values:
        raise ValueError("wildcards are not allowed in command allowlists")
    return values


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
        return cls(
            profile=profile,
            public_host=env.get("BOGDA_CONSOLE_PUBLIC_HOST", "127.0.0.1"),
            public_port=public_port,
            bff_host="127.0.0.1",
            bff_port=bff_port,
            fixture_scenario=env.get("BOGDA_CONSOLE_FIXTURE", "normal-active"),
            test_mode=env.get("BOGDA_CONSOLE_TEST_MODE", "0") == "1",
            prefect_api_url=env.get("PREFECT_API_URL"),
            prefect_api_auth_string=env.get("PREFECT_API_AUTH_STRING"),
            prefect_api_key=env.get("PREFECT_API_KEY"),
            deepseek_api_key=env.get("DEEPSEEK_API_KEY"),
            deepseek_api_base=env.get("DEEPSEEK_API_BASE", "https://api.deepseek.com"),
            replica_count=replica_count,
            allowed_deployment_ids=_exact_set(
                env.get("BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS")
            ),
            allowed_schedule_ids=_exact_set(env.get("BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS")),
            allowed_queue_ids=_exact_set(env.get("BOGDA_CONSOLE_ALLOWED_QUEUE_IDS")),
            allowed_work_pool_names=_exact_set(
                env.get("BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES")
            ),
        )

    @property
    def commands_enabled(self) -> bool:
        return self.profile in {"mock-all", "allowlisted-test"}

    @property
    def review_enabled(self) -> bool:
        return self.commands_enabled and self.replica_count == 1

    @property
    def autonomy_writes_enabled(self) -> bool:
        return self.profile == "mock-all"

    @property
    def model_control_enabled(self) -> bool:
        return self.profile == "mock-all"
