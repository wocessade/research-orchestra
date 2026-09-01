from pathlib import Path


def _maintain_sh() -> str:
    return (
        Path(__file__).resolve().parents[3]
        / "bogda"
        / "deploy"
        / "console"
        / "maintain.sh"
    ).read_text(encoding="utf-8")


def test_maintain_sh_only_allows_four_verbs() -> None:
    text = _maintain_sh()
    assert "status|logs|restart|health" in text
    assert "cat /etc" not in text
    assert "journalctl -u" in text
    assert "funnel" not in text
    assert "npm" not in text
    assert "git pull" not in text


def test_health_probes_root_assets_and_capabilities() -> None:
    text = _maintain_sh()
    assert "/api/v1/capabilities" in text
    assert "frontend/dist/assets" in text
    assert "BOGDA_CONSOLE_PUBLIC_PORT" in text
    assert '"$base/"' in text
    assert "3100" in text
    assert 'base="http://127.0.0.1:3101"' not in text


def test_restart_waits_until_loopback_answers() -> None:
    text = _maintain_sh()
    assert "systemctl restart" in text
    assert "sleep" in text
    assert "30" in text


def test_logs_include_listen_and_serve_hints() -> None:
    text = _maintain_sh()
    assert "ss " in text
    assert "tailscale serve status" in text


def test_deploy_scripts_require_fixtures() -> None:
    deploy = (
        Path(__file__).resolve().parents[3]
        / "bogda"
        / "deploy"
        / "console"
        / "deploy_console.sh"
    ).read_text(encoding="utf-8")
    remote = (
        Path(__file__).resolve().parents[3]
        / "bogda"
        / "deploy"
        / "console"
        / "remote-install.sh"
    ).read_text(encoding="utf-8")
    assert "fixtures/normal-active.json" in deploy
    assert "fixtures/normal-active.json" in remote
    assert "rk3528.tail6d8b09.ts.net" in deploy
    assert "BOGDA_CONSOLE_MAGICDNS_HOST" in deploy
    assert "BOGDA_CONSOLE_PUBLIC_PORT" in remote
    assert "DEEPSEEK_API_KEY" in remote
    assert "orchestra-broker.service.d/env.conf" in remote
    assert "echo \"$line\"" not in remote
    assert "cat /etc/bogda" not in remote
