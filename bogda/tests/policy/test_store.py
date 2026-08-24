import json

import pytest

from bogda.contracts import AutonomyMode
from bogda.policy import PolicyRevisionConflict, PolicyStore, PolicyStoreError


def test_missing_store_resolves_to_supervised_global_default(tmp_path) -> None:
    store = PolicyStore(tmp_path / "autonomy.json")

    resolved = store.resolve_mode("new-project")

    assert resolved.effective_mode is AutonomyMode.SUPERVISED
    assert resolved.mode_source == "global-default"
    assert resolved.policy_revision == 0
    assert not store.path.exists()


def test_project_override_wins_and_update_increments_revision(tmp_path) -> None:
    store = PolicyStore(tmp_path / "autonomy.json")

    global_policy = store.set_mode(
        project_id=None,
        mode=AutonomyMode.MANUAL,
        expected_revision=0,
    )
    project_policy = store.set_mode(
        project_id="alpine",
        mode=AutonomyMode.AUTONOMOUS,
        expected_revision=global_policy.revision,
    )

    assert project_policy.revision == 2
    assert store.resolve_mode("other").effective_mode is AutonomyMode.MANUAL
    resolved = store.resolve_mode("alpine")
    assert resolved.effective_mode is AutonomyMode.AUTONOMOUS
    assert resolved.mode_source == "project-override"
    assert resolved.policy_revision == 2


def test_stale_revision_does_not_overwrite_policy(tmp_path) -> None:
    store = PolicyStore(tmp_path / "autonomy.json")
    store.set_mode(None, AutonomyMode.MANUAL, expected_revision=0)

    with pytest.raises(PolicyRevisionConflict, match="expected revision 0, found 1"):
        store.set_mode(None, AutonomyMode.AUTONOMOUS, expected_revision=0)

    assert store.resolve_mode("project").effective_mode is AutonomyMode.MANUAL


def test_invalid_policy_file_fails_closed_without_rewriting_it(tmp_path) -> None:
    path = tmp_path / "autonomy.json"
    original = {"global_default": "invalid", "project_overrides": {}, "revision": 4}
    path.write_text(json.dumps(original), encoding="utf-8")
    store = PolicyStore(path)

    with pytest.raises(PolicyStoreError, match="invalid autonomy policy"):
        store.resolve_mode("project")

    assert json.loads(path.read_text(encoding="utf-8")) == original


def test_clear_project_override_restores_global_inheritance(tmp_path) -> None:
    store = PolicyStore(tmp_path / "autonomy.json")
    store.set_mode("alpine", AutonomyMode.AUTONOMOUS, expected_revision=0)

    policy = store.clear_project_override("alpine", expected_revision=1)

    assert policy.revision == 2
    resolved = store.resolve_mode("alpine")
    assert resolved.effective_mode is AutonomyMode.SUPERVISED
    assert resolved.mode_source == "global-default"
