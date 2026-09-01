from pathlib import Path


def test_prepare_runner_share_makes_inbox_and_shared_dbs_dirs() -> None:
    text = (
        Path(__file__).resolve().parents[2]
        / "deploy"
        / "shared"
        / "prepare_runner_share.sh"
    ).read_text(encoding="utf-8")
    assert "/mnt/nas/.bogda/inbox" in text
    assert "/mnt/nas/.bogda/runner/artifacts" in text
    assert "token_hex" not in text
    assert "tailscale funnel" not in text
