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
