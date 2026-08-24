from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timedelta
from typing import Any

from pydantic import ValidationError

from bogda_console.contracts.models import (
    Availability,
    Page,
    RunResultVersionSummary,
    RunResultView,
    ScientificStatus,
    ValidRunResult,
)


class ReviewConflict(Exception):
    def __init__(self, current_resource: RunResultView) -> None:
        super().__init__("the RunResult changed after the review form was opened")
        self.current_resource = current_resource


class MockRunResultAdapter:
    source_mode = "mock"

    def __init__(self, fixture: dict[str, Any]) -> None:
        self._fixture = copy.deepcopy(fixture)
        self._source = self._fixture["runResults"]
        self._clock = datetime.fromisoformat(self._fixture["clock"].replace("Z", "+00:00"))
        self._locks: dict[str, asyncio.Lock] = {}
        self.append_calls: list[str] = []

    @property
    def observed_at(self) -> datetime:
        return datetime.fromisoformat(self._source["source"]["observedAt"].replace("Z", "+00:00"))

    def _require_available(self) -> None:
        if not self._source["source"]["available"]:
            raise ConnectionError("mock RunResult source unavailable")

    async def get_latest(self, run_id: str) -> RunResultView:
        self._require_available()
        versions = self._source["artifactsByRun"].get(run_id, [])
        if not versions:
            return RunResultView(availability=Availability.MISSING, validationIssues=[])
        return self._view(versions[-1])

    async def list_versions(
        self, run_id: str, cursor: str | None, limit: int
    ) -> Page[RunResultVersionSummary]:
        self._require_available()
        versions = list(reversed(self._source["artifactsByRun"].get(run_id, [])))
        offset = int(cursor or 0)
        items = [self._version(raw) for raw in versions[offset : offset + limit]]
        next_cursor = str(offset + limit) if offset + limit < len(versions) else None
        return Page(items=items, nextCursor=next_cursor)

    async def append_review(
        self,
        run_id: str,
        base_artifact_id: str,
        scientific_status: ScientificStatus | str,
        review_summary: str | None,
    ) -> RunResultView:
        lock = self._locks.setdefault(run_id, asyncio.Lock())
        async with lock:
            current = await self.get_latest(run_id)
            if current.artifact_id != base_artifact_id:
                raise ReviewConflict(current)
            if current.availability != Availability.AVAILABLE or current.result is None:
                raise ValueError("latest RunResult is not valid")
            payload = copy.deepcopy(current.result.model_dump(mode="json"))
            payload.update(
                {
                    "scientific_status": ScientificStatus(scientific_status).value,
                    "review_summary": review_summary,
                }
            )
            versions = self._source["artifactsByRun"][run_id]
            created_at = self._clock + timedelta(seconds=len(versions) + 1)
            raw = {
                "artifactId": f"artifact-{run_id}-{len(versions) + 1}",
                "createdAt": created_at.isoformat(),
                "key": f"bogda-run-{run_id}",
                "type": "bogda.run-result",
                "payload": payload,
            }
            versions.append(raw)
            self.append_calls.append(run_id)
            return self._view(raw)

    def _view(self, raw: dict[str, Any]) -> RunResultView:
        created = datetime.fromisoformat(raw["createdAt"].replace("Z", "+00:00"))
        try:
            result = ValidRunResult.model_validate(raw["payload"])
        except ValidationError as error:
            issues = [issue["msg"] for issue in error.errors()]
            return RunResultView(
                availability=Availability.INVALID,
                artifactId=raw["artifactId"],
                artifactCreatedAt=created,
                result=None,
                validationIssues=issues,
            )
        return RunResultView(
            availability=Availability.AVAILABLE,
            artifactId=raw["artifactId"],
            artifactCreatedAt=created,
            result=result,
            validationIssues=[],
        )

    def _version(self, raw: dict[str, Any]) -> RunResultVersionSummary:
        view = self._view(raw)
        return RunResultVersionSummary(
            artifactId=raw["artifactId"],
            createdAt=view.artifact_created_at,
            availability=("available" if view.result else "invalid"),
            scientificStatus=(view.result.scientific_status if view.result else None),
            reviewSummary=(view.result.review_summary if view.result else None),
        )
