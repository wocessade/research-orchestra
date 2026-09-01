from pathlib import Path


def test_maintain_sh_only_allows_four_verbs() -> None:
    text = (
        Path(__file__).resolve().parents[3]
        / "bogda"
        / "deploy"
        / "console"
        / "maintain.sh"
    ).read_text(encoding="utf-8")
    assert "status|logs|restart|health" in text
    assert "cat /etc" not in text
    assert "journalctl -u" in text


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
    assert "rk3528.tail6d8b09.ts.net:3101" in deploy
