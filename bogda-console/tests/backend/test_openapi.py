from __future__ import annotations

from bogda_console.app import create_app
from bogda_console.config import Settings


def test_openapi_contains_every_canonical_wire_schema() -> None:
    schemas = create_app(Settings.from_env({})).openapi()["components"]["schemas"]
    required = {
        "ApiError",
        "CapabilitySnapshot",
        "DeploymentSummary",
        "InfrastructureView",
        "OverviewSnapshot",
        "PowerSnapshot",
        "QueueSnapshot",
        "RunDetail",
        "RunResultVersionSummary",
        "RunResultView",
        "RunSummary",
        "SourceMeta",
    }
    assert required <= set(schemas)


def test_openapi_keeps_command_and_review_request_bodies_closed() -> None:
    schema = create_app(Settings.from_env({})).openapi()
    paths = schema["paths"]
    assert paths["/api/v1/runs/{run_id}/cancel"]["post"]["requestBody"]
    assert paths["/api/v1/runs/{run_id}/reviews"]["post"]["requestBody"]
