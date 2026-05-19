from fastapi.testclient import TestClient

from pawcare.api import create_app, create_local_app
from pawcare.services import (
    InMemoryPetRepository,
    PetRecord,
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
    assert "User ID" not in page_response.text
    assert "Pet ID" not in page_response.text
    assert "Add pet" in page_response.text
    assert "Add Observation" in page_response.text
    assert "Save Observation" in page_response.text
    assert "Type a message..." in page_response.text
    assert "Modify Care Plan" in page_response.text
    assert "Modify" in page_response.text
    assert "Potty time" in page_response.text
    assert "Potty before bed" in page_response.text
    assert "Afternoon activity" in page_response.text
    assert "Morning walk" in page_response.text
    assert "Add medication" in page_response.text
    assert "Use local photo" in page_response.text
    assert "Health baseline" in page_response.text
    assert js_response.status_code == 200
    assert "sendPetMessage" in js_response.text
    assert "duplicateMealWarning" in js_response.text
    assert "avatar_image" in js_response.text
    assert "addMedicationField" in js_response.text
    assert "Pet profile" not in js_response.text
    assert css_response.status_code == 200
    assert ".app-shell" in css_response.text
    assert ".chat-bubble" in css_response.text
    assert ".observation-types" in css_response.text


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
                "avatar": "collie",
                "avatar_image": None,
                "observation_count": 0,
            },
            {
                "pet_id": "dog_bear",
                "name": "Bear",
                "avatar": "collie",
                "avatar_image": None,
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
