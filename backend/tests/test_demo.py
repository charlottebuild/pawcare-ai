from pawcare.demo import build_demo_workspace, process_demo_message


def test_demo_workspace_seeds_user_and_two_pets() -> None:
    workspace = build_demo_workspace()

    pets = workspace.repository.list_pets(user_id=workspace.user.user_id)
    assert workspace.user.user_id == "user_demo"
    assert sorted(pet.pet_id for pet in pets) == ["dog_bear", "dog_mochi"]
    assert all(pet.observations == [] for pet in pets)


def test_process_demo_message_returns_response_and_stored_observations() -> None:
    result = process_demo_message(raw_text="Mochi barely touched breakfast.")

    response = result["response"]
    assert isinstance(response, dict)
    assert response["status"] == "attention_needed"
    assert response["dog_id"] == "dog_mochi"
    assert "GL_APPETITE_002" in response["source_guideline_ids"]
    assert result["stored_observation_count"] == 1
    assert result["stored_observation_categories"] == ["food_intake"]
