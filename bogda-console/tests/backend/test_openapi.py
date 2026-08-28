from __future__ import annotations

from bogda_console.app import create_app
from bogda_console.config import Settings


def _deref_schema(schema: dict, schemas: dict) -> dict:
    if "$ref" in schema:
        return schemas[schema["$ref"].split("/")[-1]]
    for key in ("anyOf", "oneOf", "allOf"):
        if key in schema:
            for option in schema[key]:
                if option.get("type") != "null":
                    return _deref_schema(option, schemas)
    return schema


def test_openapi_contains_every_canonical_wire_schema() -> None:
    schemas = create_app(Settings.from_env({})).openapi()["components"]["schemas"]
    required = {
        "ApiError",
        "AutonomyPolicySnapshot",
        "CapabilitySnapshot",
        "DecisionCenterSnapshot",
        "ModelBudgetSnapshot",
        "ModelPolicySnapshot",
        "RunPreparationPreview",
        "DeploymentSummary",
        "InfrastructureView",
        "OverviewSnapshot",
        "PowerSnapshot",
        "QueueSnapshot",
        "RunDetail",
        "RunResultVersionSummary",
        "RunResultView",
        "RunSummary",
        "ResearchCheckpointView",
        "SourceMeta",
    }
    assert required <= set(schemas)


def test_openapi_keeps_command_and_review_request_bodies_closed() -> None:
    schema = create_app(Settings.from_env({})).openapi()
    paths = schema["paths"]
    assert paths["/api/v1/runs/{run_id}/cancel"]["post"]["requestBody"]
    assert paths["/api/v1/runs/{run_id}/reviews"]["post"]["requestBody"]
    assert paths["/api/v1/runs/{run_id}/checkpoints"]["post"]["requestBody"]
    assert paths["/api/v1/run-preparations/preview"]["post"]["requestBody"]
    assert paths["/api/v1/model-policy/global"]["post"]["requestBody"]

    schemas = schema["components"]["schemas"]
    new_model_control_paths = (
        "/api/v1/decisions/{decision_id}",
        "/api/v1/model-policy/global",
        "/api/v1/model-policy/projects/{project_id}",
        "/api/v1/run-preparations/preview",
    )
    for path in new_model_control_paths:
        body_schema = paths[path]["post"]["requestBody"]["content"]["application/json"]["schema"]
        assert _deref_schema(body_schema, schemas)["additionalProperties"] is False, path


def test_openapi_model_control_mutations_use_typed_receipts() -> None:
    schemas = create_app(Settings.from_env({})).openapi()["components"]["schemas"]
    decision_envelope = schemas["ApiEnvelope_CommandReceipt_DecisionCenterSnapshot__"]
    policy_envelope = schemas["ApiEnvelope_CommandReceipt_ModelPolicySnapshot__"]
    assert decision_envelope["properties"]["data"]["anyOf"][0]["$ref"].endswith(
        "CommandReceipt_DecisionCenterSnapshot_"
    )
    assert policy_envelope["properties"]["data"]["anyOf"][0]["$ref"].endswith(
        "CommandReceipt_ModelPolicySnapshot_"
    )
    assert schemas["CommandReceipt_DecisionCenterSnapshot_"]["properties"]["snapshot"]["$ref"].endswith(
        "DecisionCenterSnapshot"
    )
    assert schemas["CommandReceipt_ModelPolicySnapshot_"]["properties"]["snapshot"]["$ref"].endswith(
        "ModelPolicySnapshot"
    )
