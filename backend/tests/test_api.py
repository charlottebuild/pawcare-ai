import json

from fastapi.testclient import TestClient

from pawcare.api import create_app, create_local_app
from pawcare.schemas.state import UserResponse
from pawcare.services import (
    InMemoryPetRepository,
    PetRecord,
    ResponsePolisher,
    SemanticCareContextCache,
    SQLitePetRepository,
    UserAccount,
)
from pawcare.schemas.state import BehavioralBaseline, DogProfile, HealthBaseline


def _client() -> TestClient:
    return TestClient(create_app(repository=InMemoryPetRepository()))


def _pet_payload(pet_id: str, name: str) -> dict[str, object]:
    return {
        "pet_id": pet_id,
        "dog_profile": {
            "id": pet_id,
            "name": name,
            "species": "dog",
            "care_notes": ["avatar:collie"],
        },
        "behavioral_baseline": {
            "general_temperament": "food_motivated",
            "social_profile": {
                "large_dog_reaction": "neutral",
                "small_dog_reaction": "friendly",
                "prey_drive_level": 4,
            },
            "resource_guarding_profile": {
                "toy_guarding": "mild",
                "known_guarded_resources": ["high_value_chews"],
            },
        },
        "health_baseline": {
            "normal_appetite": "high",
            "normal_stool_quality": "firm",
            "normal_activity_level": "medium",
        },
    }


def _create_user_and_two_pets(client: TestClient) -> None:
    response = client.post(
        "/v1/users",
        json={
            "user_id": "user_123",
            "display_name": "Charlotte",
            "email": "charlotte@example.com",
        },
    )
    assert response.status_code == 200
    for pet_id, name in [("dog_mochi", "Mochi"), ("dog_bear", "Bear")]:
        response = client.post(
            "/v1/users/user_123/pets",
            json=_pet_payload(pet_id=pet_id, name=name),
        )
        assert response.status_code == 200


def _sse_events(text: str) -> list[tuple[str, dict[str, object]]]:
    events: list[tuple[str, dict[str, object]]] = []
    for block in text.strip().split("\n\n"):
        event = "message"
        data = {}
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line.removeprefix("event:").strip()
            if line.startswith("data:"):
                data = json.loads(line.removeprefix("data:").strip())
        events.append((event, data))
    return events


def test_health_endpoint_returns_ok() -> None:
    client = _client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_redirects_to_local_app() -> None:
    client = _client()

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/app"


def test_local_app_page_and_static_assets_are_served() -> None:
    client = _client()

    page_response = client.get("/app")
    js_response = client.get("/app/static/app.js")
    css_response = client.get("/app/static/app.css")

    assert page_response.status_code == 200
    assert "PawCare" in page_response.text
    assert "/app/static/app.js" in page_response.text
    assert "/app/static/app.css" in page_response.text
    assert "User ID" not in page_response.text
    assert "Pet ID" not in page_response.text
    assert js_response.status_code == 200
    assert "PawCare Assistant" in js_response.text
    assert "Add pet" in js_response.text
    assert "Species" in js_response.text
    assert "Cat" in js_response.text
    assert "Add Observation" in js_response.text
    assert "Save Observation" in js_response.text
    assert "Type a message..." in js_response.text
    assert "Timeline" in js_response.text
    assert "Care Plan" in js_response.text
    assert "Modify Care Plan" in js_response.text
    assert "Modify" in js_response.text
    assert "Potty time" in js_response.text
    assert "Potty before bed" in js_response.text
    assert "Afternoon activity" in js_response.text
    assert "Morning walk" in js_response.text
    assert "Add medication" in js_response.text
    assert "Use local photo" in js_response.text
    assert "Drag to reposition" in js_response.text
    assert "Health baseline" in js_response.text
    assert "Domestic Shorthair" in js_response.text
    assert "avatar_image" in js_response.text
    assert "context_summary" in js_response.text
    assert "Vet reference" in js_response.text
    assert "Similar case" in js_response.text
    assert "Professional references" not in js_response.text
    assert "Similar cases" not in js_response.text
    assert "_has_triage_intent" not in js_response.text
    assert "pawcareWorkspaceV1" in js_response.text
    assert "Pet profile" not in js_response.text
    assert css_response.status_code == 200
    assert ".app-shell" in css_response.text
    assert ".chat-bubble" in css_response.text
    assert ".observation-types" in css_response.text
    assert ".observation-item-header" in css_response.text


def test_create_user_create_two_pets_and_list_pet_summaries() -> None:
    client = _client()

    _create_user_and_two_pets(client)
    response = client.get("/v1/users/user_123/pets")

    assert response.status_code == 200
    assert response.json() == {
        "pets": [
            {
                "pet_id": "dog_mochi",
                "name": "Mochi",
                "species": "dog",
                "avatar": "collie",
                "avatar_image": None,
                "avatar_zoom": 1.0,
                "avatar_x": 50.0,
                "avatar_y": 50.0,
                "observation_count": 0,
            },
            {
                "pet_id": "dog_bear",
                "name": "Bear",
                "species": "dog",
                "avatar": "collie",
                "avatar_image": None,
                "avatar_zoom": 1.0,
                "avatar_x": 50.0,
                "avatar_y": 50.0,
                "observation_count": 0,
            },
        ]
    }


def test_create_user_can_derive_user_id_from_email() -> None:
    client = _client()

    response = client.post(
        "/v1/users",
        json={"display_name": "Charlotte", "email": "charlotte@example.com"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["user_id"] == "user_charlotte_example_com"
    assert body["display_name"] == "Charlotte"
    assert body["email"] == "charlotte@example.com"


def test_create_pet_can_derive_pet_id_from_profile_id() -> None:
    client = _client()
    response = client.post("/v1/users", json={"user_id": "user_123"})
    assert response.status_code == 200

    payload = _pet_payload(pet_id="dog_system_generated", name="Mochi")
    payload.pop("pet_id")
    response = client.post("/v1/users/user_123/pets", json=payload)

    body = response.json()
    assert response.status_code == 200
    assert body["pet_id"] == "dog_system_generated"
    assert body["dog_profile"]["id"] == "dog_system_generated"


def test_create_cat_pet_preserves_species_and_cat_breed() -> None:
    client = _client()
    response = client.post("/v1/users", json={"user_id": "user_123"})
    assert response.status_code == 200

    response = client.post(
        "/v1/users/user_123/pets",
        json={
            "pet_id": "cat_niaoniao",
            "dog_profile": {
                "id": "cat_niaoniao",
                "name": "NiaoNiao",
                "species": "cat",
                "breed": "Domestic Shorthair",
                "care_notes": ["avatar:cat"],
            },
            "behavioral_baseline": {},
            "health_baseline": {},
        },
    )
    detail = response.json()
    list_response = client.get("/v1/users/user_123/pets")

    assert response.status_code == 200
    assert detail["dog_profile"]["species"] == "cat"
    assert detail["dog_profile"]["breed"] == "Domestic Shorthair"
    assert list_response.json()["pets"][0]["species"] == "cat"


def test_get_one_pet_returns_detail_without_internal_agent_state() -> None:
    client = _client()
    _create_user_and_two_pets(client)

    response = client.get("/v1/users/user_123/pets/dog_mochi")

    body = response.json()
    assert response.status_code == 200
    assert body["pet_id"] == "dog_mochi"
    assert body["dog_profile"]["name"] == "Mochi"
    assert body["observation_count"] == 0
    assert "agent_outputs" not in body
    assert "proposed_update" not in body
    assert "safety_review" not in body


def test_observations_start_empty_then_reflect_message_processing() -> None:
    client = _client()
    _create_user_and_two_pets(client)

    response = client.get("/v1/users/user_123/pets/dog_mochi/observations")
    assert response.status_code == 200
    assert response.json() == {"observations": []}

    message_response = client.post(
        "/v1/users/user_123/pets/dog_mochi/messages",
        json={
            "raw_text": "Mochi barely touched breakfast.",
            "timestamp": "2026-05-08T08:00:00-07:00",
            "workflow_id": "wf_api_001",
        },
    )
    assert message_response.status_code == 200
    assert message_response.json()["status"] == "attention_needed"

    response = client.get("/v1/users/user_123/pets/dog_mochi/observations")
    observations = response.json()["observations"]
    assert len(observations) == 1
    assert observations[0]["category"] == "food_intake"
    assert observations[0]["raw_text"] == "Mochi barely touched breakfast."

    bear_response = client.get("/v1/users/user_123/pets/dog_bear")
    assert bear_response.json()["observation_count"] == 0


def test_update_pet_profile_preserves_existing_observations() -> None:
    client = _client()
    _create_user_and_two_pets(client)
    response = client.post(
        "/v1/users/user_123/pets/dog_mochi/messages",
        json={
            "raw_text": "Mochi barely touched breakfast.",
            "timestamp": "2026-05-08T08:00:00-07:00",
            "workflow_id": "wf_api_update_pet_001",
        },
    )
    assert response.status_code == 200

    payload = _pet_payload(pet_id="dog_mochi", name="Mochi Updated")
    payload["dog_profile"]["breed"] = "Border Collie"
    payload["health_baseline"]["normal_appetite"] = "picky"
    response = client.patch("/v1/users/user_123/pets/dog_mochi", json=payload)

    body = response.json()
    assert response.status_code == 200
    assert body["dog_profile"]["name"] == "Mochi Updated"
    assert body["health_baseline"]["normal_appetite"] == "picky"
    assert body["observation_count"] == 1

    response = client.get("/v1/users/user_123/pets/dog_mochi/observations")
    assert len(response.json()["observations"]) == 1


def test_high_risk_message_returns_safe_user_response_only() -> None:
    client = _client()
    _create_user_and_two_pets(client)

    response = client.post(
        "/v1/users/user_123/pets/dog_mochi/messages",
        json={
            "raw_text": "After taking Rimadyl pain medication, Mochi had bloody stool.",
            "timestamp": "2026-05-08T09:15:00-07:00",
            "workflow_id": "wf_api_002",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "escalate"
    assert body["risk_band"] == "high"
    assert body["escalation_conditions"]
    assert "GL_NSAID_SIDE_EFFECT_001" in body["source_guideline_ids"]
    assert "dose" not in body["message"].lower()
    assert "dosage" not in body["message"].lower()
    assert "agent_outputs" not in body
    assert "proposed_update" not in body
    assert "safety_review" not in body


def test_streaming_message_returns_status_events_and_final_response() -> None:
    client = _client()
    _create_user_and_two_pets(client)

    with client.stream(
        "POST",
        "/v1/users/user_123/pets/dog_mochi/messages/stream",
        json={
            "raw_text": (
                "Mochi pulls his head back when eating, drools, and has a small "
                "lump under the tongue. Could it be salivary mucocele?"
            ),
            "timestamp": "2026-05-08T09:15:00-07:00",
            "workflow_id": "wf_api_stream_001",
        },
    ) as response:
        body = response.read().decode()

    events = _sse_events(body)
    event_names = [event for event, _ in events]
    final_payload = events[-1][1]
    final_response = final_payload["response"]

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert event_names == [
        "status",
        "status",
        "status",
        "status",
        "status",
        "final",
    ]
    assert [payload.get("stage") for _, payload in events[:-1]] == [
        "received",
        "loading_pet",
        "processing_message",
        "retrieving_care_context",
        "safety_review",
    ]
    assert final_response["status"] == "attention_needed"
    assert "GL_CONDITION_ORAL_NECK_001" in final_response["source_guideline_ids"]
    assert final_payload["care_context"]["professional_references"]
    assert final_payload["care_context"]["related_cases"]
    assert "agent_outputs" not in final_response
    assert "proposed_update" not in final_response
    assert "safety_review" not in final_response


def test_streaming_message_missing_pet_returns_generic_404_without_observations() -> None:
    client = _client()
    _create_user_and_two_pets(client)

    response = client.post(
        "/v1/users/user_123/pets/not_mochi/messages/stream",
        json={
            "raw_text": "Mochi barely touched breakfast.",
            "timestamp": "2026-05-08T08:00:00-07:00",
        },
    )

    observations = client.get("/v1/users/user_123/pets/dog_mochi/observations")

    assert response.status_code == 404
    assert response.json()["detail"] == "Pet record is not available."
    assert observations.json()["observations"] == []


def test_message_endpoint_can_use_response_polisher_without_changing_contract() -> None:
    class FakePolisher:
        def polish(
            self,
            *,
            response: UserResponse,
            care_context: dict[str, object] | None = None,
        ) -> UserResponse:
            return response.model_copy(
                update={"message": "Polished safe message."}
            )

    client = TestClient(
        create_app(
            repository=InMemoryPetRepository(),
            response_polisher=FakePolisher(),
        )
    )
    _create_user_and_two_pets(client)

    response = client.post(
        "/v1/users/user_123/pets/dog_mochi/messages",
        json={
            "raw_text": "Mochi barely touched breakfast.",
            "timestamp": "2026-05-08T08:00:00-07:00",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["message"] == "Polished safe message."
    assert body["status"] == "attention_needed"
    assert "GL_APPETITE_002" in body["source_guideline_ids"]


def test_related_cases_endpoint_returns_supporting_context_for_target_pet() -> None:
    client = _client()
    _create_user_and_two_pets(client)

    response = client.post(
        "/v1/users/user_123/pets/dog_mochi/related-cases",
        json={
            "raw_text": (
                "Mochi pulls his head back when eating, drools, and has a small "
                "lump under the tongue. Could it be salivary mucocele?"
            )
        },
    )

    body = response.json()
    first = body["related_cases"][0]
    assert response.status_code == 200
    assert "not a diagnosis" in body["disclaimer"].lower()
    assert first["case_id"] == "case_oral_neck_001"
    assert first["source_url"].startswith("https://")
    assert "salivary_gland" in first["possible_discussion_topics"]
    assert first["condition_discussion_priority"] in {
        "discuss_soon",
        "discuss_if_persistent",
    }
    assert "full_text" not in first
    assert "raw_text" not in first


def test_related_cases_do_not_change_high_risk_message_escalation() -> None:
    client = _client()
    _create_user_and_two_pets(client)

    message_response = client.post(
        "/v1/users/user_123/pets/dog_mochi/messages",
        json={
            "raw_text": "Mochi cannot pee and has blood in urine.",
            "timestamp": "2026-05-08T09:15:00-07:00",
            "workflow_id": "wf_api_cases_001",
        },
    )
    cases_response = client.post(
        "/v1/users/user_123/pets/dog_mochi/related-cases",
        json={"raw_text": "Mochi cannot pee and has blood in urine. Should I worry?"},
    )

    assert message_response.status_code == 200
    assert message_response.json()["status"] == "escalate"
    assert cases_response.status_code == 200
    assert cases_response.json()["related_cases"][0]["case_id"] == "case_urinary_001"


def test_related_cases_missing_or_unauthorized_pet_returns_generic_404() -> None:
    repository = InMemoryPetRepository()
    repository.create_user(UserAccount(user_id="user_123"))
    repository.create_user(UserAccount(user_id="user_456"))
    repository.create_pet(
        PetRecord(
            pet_id="dog_luna",
            user_id="user_456",
            dog_profile=DogProfile(id="dog_luna", name="Luna", species="dog"),
            behavioral_baseline=BehavioralBaseline(),
            health_baseline=HealthBaseline(),
        )
    )
    client = TestClient(create_app(repository=repository))

    missing_response = client.post(
        "/v1/users/user_123/pets/dog_missing/related-cases",
        json={"raw_text": "limping after surgery"},
    )
    unauthorized_response = client.post(
        "/v1/users/user_123/pets/dog_luna/related-cases",
        json={"raw_text": "limping after surgery"},
    )

    assert missing_response.status_code == 404
    assert unauthorized_response.status_code == 404


def test_care_context_endpoint_returns_professional_references_and_cases() -> None:
    client = _client()
    _create_user_and_two_pets(client)

    response = client.post(
        "/v1/users/user_123/pets/dog_mochi/care-context",
        json={
            "raw_text": (
                "Mochi pulls his head back when eating, drools, and has a small "
                "lump under the tongue. Could it be salivary mucocele?"
            )
        },
    )

    body = response.json()
    reference = body["professional_references"][0]
    case = body["related_cases"][0]
    assert response.status_code == 200
    assert "not a diagnosis" in body["non_diagnostic_notice"].lower()
    assert "not a diagnosis" in body["context_summary"].lower()
    assert reference["domain"] == "oral_neck"
    assert reference["source_url"].startswith("https://")
    assert reference["what_to_record"]
    assert "full_text" not in reference
    assert case["case_id"] == "case_oral_neck_001"
    assert body["cache_status"] == "miss"


def test_care_context_endpoint_uses_semantic_cache_for_similar_queries() -> None:
    cache = SemanticCareContextCache()
    client = TestClient(
        create_app(
            repository=InMemoryPetRepository(),
            care_context_cache=cache,
        )
    )
    _create_user_and_two_pets(client)

    first = client.post(
        "/v1/users/user_123/pets/dog_mochi/care-context",
        json={"raw_text": "Mochi poo blood this morning."},
    )
    second = client.post(
        "/v1/users/user_123/pets/dog_mochi/care-context",
        json={"raw_text": "Mochi had bloody stool this morning."},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["cache_status"] == "miss"
    assert second.json()["cache_status"] == "hit"
    assert second.json()["professional_references"][0]["domain"] == "gi"
    for forbidden_field in (
        "response",
        "status",
        "risk_band",
        "source_guideline_ids",
        "escalation_conditions",
        "agent_outputs",
        "proposed_update",
        "safety_review",
    ):
        assert forbidden_field not in second.json()


def test_care_context_endpoint_returns_urinary_context_for_cat_red_flag() -> None:
    client = _client()
    response = client.post("/v1/users", json={"user_id": "user_123"})
    assert response.status_code == 200
    response = client.post(
        "/v1/users/user_123/pets",
        json={
            "pet_id": "cat_niaoniao",
            "dog_profile": {
                "id": "cat_niaoniao",
                "name": "NiaoNiao",
                "species": "cat",
                "breed": "Domestic Shorthair",
                "care_notes": ["avatar:cat"],
            },
            "behavioral_baseline": {},
            "health_baseline": {},
        },
    )
    assert response.status_code == 200

    response = client.post(
        "/v1/users/user_123/pets/cat_niaoniao/care-context",
        json={
            "raw_text": (
                "NiaoNiao couldnt' pee today and did not pee all day. "
                "Is there any problem?"
            )
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert "urinary" in body["context_summary"].lower()
    assert body["professional_references"][0]["domain"] == "urinary"
    assert body["related_cases"][0]["case_id"] == "case_urinary_001"
    assert "diagnosis" in body["non_diagnostic_notice"].lower()


def test_care_context_endpoint_returns_urinary_context_for_no_bathroom_update() -> None:
    client = _client()
    response = client.post("/v1/users", json={"user_id": "user_123"})
    assert response.status_code == 200
    response = client.post(
        "/v1/users/user_123/pets",
        json={
            "pet_id": "cat_niaoniao",
            "dog_profile": {
                "id": "cat_niaoniao",
                "name": "NiaoNiao",
                "species": "cat",
                "breed": "Domestic Shorthair",
                "care_notes": ["avatar:cat"],
            },
            "behavioral_baseline": {},
            "health_baseline": {},
        },
    )
    assert response.status_code == 200

    response = client.post(
        "/v1/users/user_123/pets/cat_niaoniao/care-context",
        json={"raw_text": "猫猫一天没上厕所"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["professional_references"][0]["domain"] == "urinary"
    assert body["related_cases"][0]["case_id"] == "case_urinary_001"


def test_care_context_endpoint_returns_gi_context_for_poo_blood_phrase() -> None:
    client = _client()
    _create_user_and_two_pets(client)

    response = client.post(
        "/v1/users/user_123/pets/dog_mochi/care-context",
        json={"raw_text": "Niao Niao poo blood this morning."},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["professional_references"][0]["domain"] == "gi"
    assert body["related_cases"][0]["case_id"] == "case_gi_001"


def test_care_context_plain_update_returns_empty_context() -> None:
    cache = SemanticCareContextCache()
    client = TestClient(
        create_app(
            repository=InMemoryPetRepository(),
            care_context_cache=cache,
        )
    )
    _create_user_and_two_pets(client)

    response = client.post(
        "/v1/users/user_123/pets/dog_mochi/care-context",
        json={"raw_text": "Mochi did not have breakfast this morning."},
    )

    assert response.status_code == 200
    assert response.json()["context_summary"] == ""
    assert response.json()["professional_references"] == []
    assert response.json()["related_cases"] == []
    assert response.json()["cache_status"] == "miss"
    assert len(cache) == 0


def test_message_endpoint_does_not_use_semantic_cache_for_final_response() -> None:
    cache = SemanticCareContextCache()
    client = TestClient(
        create_app(
            repository=InMemoryPetRepository(),
            care_context_cache=cache,
        )
    )
    _create_user_and_two_pets(client)

    care_context = client.post(
        "/v1/users/user_123/pets/dog_mochi/care-context",
        json={"raw_text": "Mochi poo blood this morning."},
    )
    message = client.post(
        "/v1/users/user_123/pets/dog_mochi/messages",
        json={
            "raw_text": "Mochi poo blood this morning.",
            "timestamp": "2026-05-08T08:00:00-07:00",
        },
    )

    assert care_context.json()["cache_status"] == "miss"
    assert message.status_code == 200
    assert message.json()["status"] == "escalate"
    assert "GL_STOOL_001" in message.json()["source_guideline_ids"]
    assert "cache_status" not in message.json()


def test_care_context_missing_or_unauthorized_pet_returns_generic_404() -> None:
    repository = InMemoryPetRepository()
    repository.create_user(UserAccount(user_id="user_123"))
    repository.create_user(UserAccount(user_id="user_456"))
    repository.create_pet(
        PetRecord(
            pet_id="dog_luna",
            user_id="user_456",
            dog_profile=DogProfile(id="dog_luna", name="Luna", species="dog"),
            behavioral_baseline=BehavioralBaseline(),
            health_baseline=HealthBaseline(),
        )
    )
    client = TestClient(create_app(repository=repository))

    missing_response = client.post(
        "/v1/users/user_123/pets/dog_missing/care-context",
        json={"raw_text": "limping after surgery, should I worry?"},
    )
    unauthorized_response = client.post(
        "/v1/users/user_123/pets/dog_luna/care-context",
        json={"raw_text": "limping after surgery, should I worry?"},
    )

    assert missing_response.status_code == 404
    assert unauthorized_response.status_code == 404


def test_missing_or_unauthorized_pet_returns_generic_404_without_appending() -> None:
    repository = InMemoryPetRepository()
    repository.create_user(UserAccount(user_id="user_123"))
    repository.create_user(UserAccount(user_id="user_456"))
    repository.create_pet(
        PetRecord(
            pet_id="dog_luna",
            user_id="user_456",
            dog_profile=DogProfile(id="dog_luna", name="Luna", species="dog"),
            behavioral_baseline=BehavioralBaseline(),
            health_baseline=HealthBaseline(),
        )
    )
    client = TestClient(create_app(repository=repository))

    missing_response = client.post(
        "/v1/users/user_123/pets/dog_missing/messages",
        json={
            "raw_text": "Barely ate breakfast.",
            "timestamp": "2026-05-08T08:00:00-07:00",
        },
    )
    unauthorized_response = client.get("/v1/users/user_123/pets/dog_luna")

    assert missing_response.status_code == 404
    assert unauthorized_response.status_code == 404
    assert repository.get_pet(user_id="user_456", pet_id="dog_luna").observations == []


def test_basic_validation_rejects_blank_pet_id_raw_text_and_invalid_timestamp() -> None:
    client = _client()
    _create_user_and_two_pets(client)

    blank_pet_response = client.post(
        "/v1/users/user_123/pets/%20%20/messages",
        json={
            "raw_text": "Barely ate breakfast.",
            "timestamp": "2026-05-08T08:00:00-07:00",
        },
    )
    blank_text_response = client.post(
        "/v1/users/user_123/pets/dog_mochi/messages",
        json={
            "raw_text": "   ",
            "timestamp": "2026-05-08T08:00:00-07:00",
        },
    )
    bad_timestamp_response = client.post(
        "/v1/users/user_123/pets/dog_mochi/messages",
        json={
            "raw_text": "Barely ate breakfast.",
            "timestamp": "not-a-timestamp",
        },
    )
    blank_create_pet_response = client.post(
        "/v1/users/user_123/pets",
        json=_pet_payload(pet_id="   ", name="Blank"),
    )

    assert blank_pet_response.status_code == 422
    assert blank_text_response.status_code == 422
    assert bad_timestamp_response.status_code == 422
    assert blank_create_pet_response.status_code == 422


def test_api_can_use_sqlite_repository_for_persistent_observations(tmp_path) -> None:
    db_path = tmp_path / "pawcare.sqlite3"
    client = TestClient(create_app(repository=SQLitePetRepository(db_path)))
    response = client.post(
        "/v1/users",
        json={"user_id": "user_123", "display_name": "Charlotte"},
    )
    assert response.status_code == 200
    response = client.post(
        "/v1/users/user_123/pets",
        json=_pet_payload(pet_id="dog_mochi", name="Mochi"),
    )
    assert response.status_code == 200
    response = client.post(
        "/v1/users/user_123/pets/dog_mochi/messages",
        json={
            "raw_text": "Mochi barely touched breakfast.",
            "timestamp": "2026-05-08T08:00:00-07:00",
            "workflow_id": "wf_api_sqlite_001",
        },
    )
    assert response.status_code == 200

    reopened_client = TestClient(create_app(repository=SQLitePetRepository(db_path)))
    response = reopened_client.get("/v1/users/user_123/pets/dog_mochi/observations")
    observations = response.json()["observations"]

    assert response.status_code == 200
    assert len(observations) == 1
    assert observations[0]["category"] == "food_intake"


def test_create_local_app_uses_sqlite_persistence(tmp_path) -> None:
    db_path = tmp_path / "pawcare.local.sqlite3"
    client = TestClient(create_local_app(db_path=db_path))

    response = client.post(
        "/v1/users",
        json={"user_id": "user_123", "display_name": "Charlotte"},
    )
    assert response.status_code == 200
    response = client.post(
        "/v1/users/user_123/pets",
        json=_pet_payload(pet_id="dog_mochi", name="Mochi"),
    )
    assert response.status_code == 200
    response = client.post(
        "/v1/users/user_123/pets/dog_mochi/messages",
        json={
            "raw_text": "Mochi barely touched breakfast.",
            "timestamp": "2026-05-08T08:00:00-07:00",
            "workflow_id": "wf_local_app_001",
        },
    )
    assert response.status_code == 200

    reopened_client = TestClient(create_local_app(db_path=db_path))
    response = reopened_client.get("/v1/users/user_123/pets")
    assert response.status_code == 200
    assert response.json()["pets"][0]["observation_count"] == 1

    response = reopened_client.get("/v1/users/user_123/pets/dog_mochi/observations")
    observations = response.json()["observations"]

    assert response.status_code == 200
    assert len(observations) == 1
    assert observations[0]["raw_text"] == "Mochi barely touched breakfast."
