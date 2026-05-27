from fastapi import HTTPException

from backend.api import registry
from capsulelab.services import registry_service


def test_publish_plan_for_ghcr_includes_login_tag_and_push():
    plan = registry_service.publish_plan(
        "ghcr",
        source_image="demo:dev",
        namespace="octo-org",
        repository="demo",
        tag="v1",
    )

    assert plan["target_image"] == "ghcr.io/octo-org/demo:v1"
    assert plan["commands"] == [
        "docker login ghcr.io",
        "docker tag demo:dev ghcr.io/octo-org/demo:v1",
        "docker push ghcr.io/octo-org/demo:v1",
    ]
    assert plan["requires_token"] is True
    assert "personal access token" in plan["credential_hint"].lower()


def test_publish_plan_for_dockerhub_uses_namespace_repository_tag():
    plan = registry_service.publish_plan("dockerhub", "demo:dev", "alice", "demo", "latest")

    assert plan["target_image"] == "alice/demo:latest"
    assert plan["host"] == "docker.io"


def test_publish_plan_rejects_unknown_registry():
    try:
        registry_service.publish_plan("unknown", "demo:dev", "alice", "demo")
    except ValueError as exc:
        assert "Unknown registry" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_publish_plan_endpoint_maps_validation_error():
    try:
        registry.registry_publish_plan(
            registry.RegistryPublishPlanRequest(
                registry="unknown",
                source_image="demo:dev",
                namespace="alice",
                repository="demo",
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("Expected HTTPException")
