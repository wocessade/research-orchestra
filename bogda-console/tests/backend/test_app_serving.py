from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from bogda_console.__main__ import main
from bogda_console.app import create_app
from bogda_console.config import Settings


def settings(**overrides: str) -> Settings:
    env = {
        "BOGDA_CONSOLE_PROFILE": "mock-all",
        "BOGDA_CONSOLE_FIXTURE": "normal-active",
        **overrides,
    }
    return Settings.from_env(env)


def test_cli_refuses_reserved_public_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOGDA_CONSOLE_PUBLIC_PORT", "3100")
    with pytest.raises(ValueError, match="3100 is reserved"):
        main([])


def test_cli_refuses_reserved_internal_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOGDA_CONSOLE_BFF_PORT", "3100")
    with pytest.raises(ValueError, match="3100 is reserved"):
        main(["--api-only"])


def test_production_frontend_requires_a_completed_build(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="npm run build"):
        create_app(settings(), frontend_dist=tmp_path)


@pytest.mark.asyncio
async def test_spa_fallback_serves_built_index_without_masking_api(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<title>Bogda Console</title>", encoding="utf-8")
    (tmp_path / "assets" / "app.js").write_text("console.info('bogda')", encoding="utf-8")
    app = create_app(settings(), frontend_dist=tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        detail = await client.get("/runs/run-1")
        asset = await client.get("/assets/app.js")
        missing_api = await client.get("/api/does-not-exist")
    assert detail.status_code == 200
    assert "Bogda Console" in detail.text
    assert asset.status_code == 200
    assert missing_api.status_code == 404


def test_real_profile_requires_an_explicit_prefect_api_url() -> None:
    with pytest.raises(ValueError, match="PREFECT_API_URL"):
        create_app(settings(BOGDA_CONSOLE_PROFILE="real-readonly"))
