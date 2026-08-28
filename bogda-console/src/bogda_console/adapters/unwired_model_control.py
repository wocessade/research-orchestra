from __future__ import annotations

from typing import Any

from bogda_console.contracts.ports import ModelControlUnavailable


class UnwiredModelControlAdapter:
    """Explicit real-profile boundary; it never falls back to mock state."""

    def _unavailable(self) -> None:
        raise ModelControlUnavailable("real model-control backend is not wired")

    async def decision_center(self) -> Any:
        self._unavailable()

    async def run_budget(self, run_id: str) -> Any:
        self._unavailable()

    async def model_policy(self, project_id: str | None = None) -> Any:
        self._unavailable()

    async def preview_run(self, *args: Any, **kwargs: Any) -> Any:
        self._unavailable()

    async def resolve_decision(self, *args: Any, **kwargs: Any) -> Any:
        self._unavailable()

    async def set_global_policy(self, *args: Any, **kwargs: Any) -> Any:
        self._unavailable()

    async def set_project_policy(self, *args: Any, **kwargs: Any) -> Any:
        self._unavailable()

    async def confirm_preparation(self, *args: Any, **kwargs: Any) -> Any:
        self._unavailable()
