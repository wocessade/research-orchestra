import json
from pathlib import Path
from typing import Mapping

from pydantic import ValidationError

from bogda.contracts import AutonomyMode
from bogda.policy.models import (
    AutonomyPolicy,
    ModelPolicy,
    ModelPolicyValues,
    ResolvedAutonomyMode,
    ResolvedModelPolicy,
)


class PolicyStoreError(RuntimeError):
    pass


class PolicyRevisionConflict(PolicyStoreError):
    pass


class ModelPolicyRevisionConflict(PolicyStoreError):
    pass


class PolicyStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> AutonomyPolicy:
        if not self.path.exists():
            return AutonomyPolicy()
        try:
            return AutonomyPolicy.model_validate_json(
                self.path.read_text(encoding="utf-8")
            )
        except (OSError, ValidationError, ValueError) as error:
            raise PolicyStoreError(
                f"invalid autonomy policy: {self.path}"
            ) from error

    def resolve_mode(self, project_id: str) -> ResolvedAutonomyMode:
        policy = self.load()
        if project_id in policy.project_overrides:
            mode = policy.project_overrides[project_id]
            source = "project-override"
        else:
            mode = policy.global_default
            source = "global-default"
        return ResolvedAutonomyMode(
            project_id=project_id,
            effective_mode=mode,
            mode_source=source,
            policy_revision=policy.revision,
        )

    def set_mode(
        self,
        project_id: str | None,
        mode: AutonomyMode,
        *,
        expected_revision: int,
    ) -> AutonomyPolicy:
        current = self.load()
        if current.revision != expected_revision:
            raise PolicyRevisionConflict(
                f"expected revision {expected_revision}, found {current.revision}"
            )
        if project_id is None:
            updated = current.model_copy(
                update={
                    "global_default": AutonomyMode(mode),
                    "revision": current.revision + 1,
                }
            )
        else:
            overrides = dict(current.project_overrides)
            overrides[project_id] = AutonomyMode(mode)
            updated = current.model_copy(
                update={
                    "project_overrides": overrides,
                    "revision": current.revision + 1,
                }
            )
        self._write(updated)
        return updated

    def clear_project_override(
        self,
        project_id: str,
        *,
        expected_revision: int,
    ) -> AutonomyPolicy:
        current = self.load()
        if current.revision != expected_revision:
            raise PolicyRevisionConflict(
                f"expected revision {expected_revision}, found {current.revision}"
            )
        overrides = dict(current.project_overrides)
        overrides.pop(project_id, None)
        updated = current.model_copy(
            update={
                "project_overrides": overrides,
                "revision": current.revision + 1,
            }
        )
        self._write(updated)
        return updated

    def _write(self, policy: AutonomyPolicy) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        temporary.write_text(
            json.dumps(policy.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)


class ModelPolicyStore:
    """Revision-guarded JSON store for the model-routing policy."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> ModelPolicy:
        if not self.path.exists():
            return ModelPolicy()
        try:
            return ModelPolicy.model_validate_json(self.path.read_text(encoding="utf-8"))
        except (OSError, ValidationError, ValueError) as error:
            raise PolicyStoreError(f"invalid model policy: {self.path}") from error

    def resolve(self, project_id: str | None) -> ResolvedModelPolicy:
        policy = self.load()
        if project_id is not None and project_id in policy.project_overrides:
            return ResolvedModelPolicy(
                project_id=project_id,
                values=policy.project_overrides[project_id],
                source="project",
                inherits_global=False,
                policy_revision=policy.revision,
            )
        return ResolvedModelPolicy(
            project_id=project_id,
            values=policy.global_default,
            source="global",
            inherits_global=True,
            policy_revision=policy.revision,
        )

    def set_global(
        self, patch: Mapping[str, object], *, expected_revision: int
    ) -> ModelPolicy:
        current = self.load()
        self._require_revision(current, expected_revision)
        merged = self._merge(current.global_default, patch)
        updated = current.model_copy(
            update={"global_default": merged, "revision": current.revision + 1}
        )
        self._write(updated)
        return updated

    def set_project(
        self,
        project_id: str,
        patch: Mapping[str, object] | None,
        *,
        expected_revision: int,
    ) -> ModelPolicy:
        current = self.load()
        self._require_revision(current, expected_revision)
        overrides = dict(current.project_overrides)
        if patch is None:
            overrides.pop(project_id, None)
        else:
            base = overrides.get(project_id, current.global_default)
            overrides[project_id] = self._merge(base, patch)
        updated = current.model_copy(
            update={"project_overrides": overrides, "revision": current.revision + 1}
        )
        self._write(updated)
        return updated

    @staticmethod
    def _require_revision(policy: ModelPolicy, expected_revision: int) -> None:
        if policy.revision != expected_revision:
            raise ModelPolicyRevisionConflict(
                f"expected revision {expected_revision}, found {policy.revision}"
            )

    @staticmethod
    def _merge(base: ModelPolicyValues, patch: Mapping[str, object]) -> ModelPolicyValues:
        if not patch:
            raise PolicyStoreError("model policy patch must not be empty")
        return ModelPolicyValues.model_validate({**base.model_dump(), **dict(patch)})

    def _write(self, policy: ModelPolicy) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        temporary.write_text(
            json.dumps(policy.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)
