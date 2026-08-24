import json
from pathlib import Path

from pydantic import ValidationError

from bogda.contracts import AutonomyMode
from bogda.policy.models import AutonomyPolicy, ResolvedAutonomyMode


class PolicyStoreError(RuntimeError):
    pass


class PolicyRevisionConflict(PolicyStoreError):
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
