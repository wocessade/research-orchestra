from decimal import Decimal

import pytest
from pydantic import ValidationError

from bogda.contracts import ModelTier
from bogda.policy import (
    ModelPolicyRevisionConflict,
    ModelPolicyStore,
    PolicyStoreError,
)


def test_defaults_are_safe_and_empty(tmp_path) -> None:
    store = ModelPolicyStore(tmp_path / "model-policy.json")
    policy = store.load()
    assert policy.revision == 0
    assert policy.global_default.default_model_tier is ModelTier.AUTO
    assert policy.global_default.minimum_remaining == Decimal("10.00")
    assert policy.global_default.workload_safety_margin == Decimal("1.20")
    assert policy.project_overrides == {}


def test_set_global_merges_patch_and_bumps_revision(tmp_path) -> None:
    path = tmp_path / "model-policy.json"
    store = ModelPolicyStore(path)
    updated = store.set_global(
        {"default_model_tier": "pro", "minimum_remaining": "25"},
        expected_revision=0,
    )
    assert updated.revision == 1
    assert updated.global_default.default_model_tier is ModelTier.PRO
    assert updated.global_default.minimum_remaining == Decimal("25")
    assert updated.global_default.prefer_off_peak is True
    assert ModelPolicyStore(path).load() == updated


def test_stale_revision_is_rejected_without_writing(tmp_path) -> None:
    path = tmp_path / "model-policy.json"
    store = ModelPolicyStore(path)
    store.set_global({"auto_resume": False}, expected_revision=0)
    with pytest.raises(ModelPolicyRevisionConflict):
        store.set_global({"auto_resume": True}, expected_revision=0)
    assert store.load().global_default.auto_resume is False
    assert store.load().revision == 1


def test_project_override_layers_on_global_and_clears_back(tmp_path) -> None:
    store = ModelPolicyStore(tmp_path / "model-policy.json")
    store.set_global(
        {"default_model_tier": "flash", "minimum_remaining": "30"},
        expected_revision=0,
    )
    store.set_project(
        "bogda-main", {"allow_flash_downgrade": False}, expected_revision=1
    )
    resolved = store.resolve("bogda-main")
    assert resolved.source == "project"
    assert resolved.inherits_global is False
    assert resolved.values.minimum_remaining == Decimal("30")
    assert resolved.values.allow_flash_downgrade is False
    assert resolved.policy_revision == 2

    store.set_project("bogda-main", None, expected_revision=2)
    resolved = store.resolve("bogda-main")
    assert resolved.source == "global"
    assert resolved.inherits_global is True
    assert resolved.values.allow_flash_downgrade is True


def test_global_source_when_project_has_no_override(tmp_path) -> None:
    store = ModelPolicyStore(tmp_path / "model-policy.json")
    resolved = store.resolve("bogda-main")
    assert resolved.source == "global"
    assert resolved.inherits_global is True
    assert resolved.project_id == "bogda-main"


def test_float_money_and_unknown_fields_are_rejected(tmp_path) -> None:
    store = ModelPolicyStore(tmp_path / "model-policy.json")
    with pytest.raises(ValidationError):
        store.set_global({"minimum_remaining": 10.0}, expected_revision=0)
    with pytest.raises(ValidationError):
        store.set_global({"unknown_field": True}, expected_revision=0)
    with pytest.raises(ValidationError):
        store.set_global({"default_model_tier": "turbo"}, expected_revision=0)
    with pytest.raises(ValidationError):
        store.set_global({"workload_safety_margin": "0.5"}, expected_revision=0)
    assert store.load().revision == 0


def test_empty_patch_is_rejected(tmp_path) -> None:
    store = ModelPolicyStore(tmp_path / "model-policy.json")
    with pytest.raises(PolicyStoreError):
        store.set_global({}, expected_revision=0)


def test_corrupt_file_fails_closed(tmp_path) -> None:
    path = tmp_path / "model-policy.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(PolicyStoreError):
        ModelPolicyStore(path).load()
