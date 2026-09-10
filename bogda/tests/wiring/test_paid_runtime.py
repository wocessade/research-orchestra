import pytest

from bogda.model_runtime import PaidModelCallService
from bogda.wiring import paid_runtime
from bogda.wiring.store_api import RemoteBudgetService, RemoteUsageUnknownRecovery

KEY_HEX = "ab" * 32


def test_factory_requires_store_env(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("BOGDA_STORE_API_URL", raising=False)
    monkeypatch.delenv("BOGDA_APPROVAL_HMAC_KEY", raising=False)
    monkeypatch.delenv("BOGDA_ARTIFACT_ROOT", raising=False)

    with pytest.raises(RuntimeError, match="BOGDA_STORE_API_URL"):
        paid_runtime.build_paid_service_from_env(run_id="run-1")


def test_factory_requires_hex_hmac_key(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BOGDA_STORE_API_URL", "http://127.0.0.1:3101")
    monkeypatch.setenv("BOGDA_APPROVAL_HMAC_KEY", "not-hex")
    monkeypatch.setenv("BOGDA_ARTIFACT_ROOT", str(tmp_path))

    with pytest.raises(RuntimeError, match="must be hex"):
        paid_runtime.build_paid_service_from_env(run_id="run-1")


def test_factory_builds_service_with_remote_stores(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BOGDA_STORE_API_URL", "http://127.0.0.1:3101")
    monkeypatch.setenv("BOGDA_APPROVAL_HMAC_KEY", KEY_HEX)
    monkeypatch.setenv("BOGDA_ARTIFACT_ROOT", str(tmp_path))
    monkeypatch.setenv("BOGDA_DSH_PATCH_DIR", str(tmp_path / "patches"))

    service = paid_runtime.build_paid_service_from_env(run_id="run-1")

    assert isinstance(service, PaidModelCallService)
    assert isinstance(service._budget, RemoteBudgetService)
    assert isinstance(service._recovery, RemoteUsageUnknownRecovery)
    assert (tmp_path / "run-1").parent == tmp_path
