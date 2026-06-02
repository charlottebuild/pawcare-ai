from pawcare.schemas.state import BehavioralBaseline, DogProfile, HealthBaseline, Observation
from pawcare.services import InMemoryPetRepository, PetRecord, SummaryWorker, UserAccount


def _observation(*, observation_id: str, raw_text: str, timestamp: str, category: str, health_context=None) -> Observation:
    return Observation.model_validate(
        {
                "observation_id": observation_id,
                "timestamp": timestamp,
                "source": "user_log",
                "category": category,
                "raw_text": raw_text,
                "confidence": 0.9,
                "severity_score": 7,
                "health_context": health_context or {},
        }
    )


def _pet(observations: list[Observation]) -> PetRecord:
    return PetRecord(
        user_id="user_123",
        pet_id="dog_mochi",
        dog_profile=DogProfile(id="dog_mochi", name="Mochi", species="dog", breed="poodle"),
        behavioral_baseline=BehavioralBaseline(),
        health_baseline=HealthBaseline(normal_appetite="high"),
        observations=observations,
    )


def test_summary_worker_builds_daily_weekly_monthly_pet_memory() -> None:
    pet = _pet(
        [
            _observation(
                observation_id="obs_001",
                raw_text="Mochi had bloody stool.",
                timestamp="2026-05-08T08:00:00-07:00",
                category="stool",
                health_context={"stool_quality": "bloody"},
            ),
            _observation(
                observation_id="obs_002",
                raw_text="Mochi did not put weight on her leg.",
                timestamp="2026-05-09T08:00:00-07:00",
                category="mobility",
                health_context={"weight_bearing": "non_weight_bearing"},
            ),
        ]
    )

    worker = SummaryWorker()
    daily = worker.build_daily_summaries(pet=pet)
    weekly = worker.build_weekly_summaries(pet=pet)
    monthly = worker.build_monthly_summaries(pet=pet)

    assert [summary.date for summary in daily] == ["2026-05-08", "2026-05-09"]
    assert "bloody stool" in daily[0].active_issues
    assert "non-weight-bearing mobility change" in daily[1].active_issues
    assert weekly[0].observation_count == 2
    assert monthly[0].month == "2026-05"


def test_context_snapshot_uses_summaries_not_full_observation_timeline() -> None:
    repository = InMemoryPetRepository()
    repository.create_user(UserAccount(user_id="user_123"))
    repository.create_pet(
        _pet(
            [
                _observation(
                    observation_id=f"obs_{index:03d}",
                    raw_text=f"Historical observation {index} with bloody stool.",
                    timestamp=f"2026-05-{index:02d}T08:00:00-07:00",
                    category="stool",
                    health_context={"stool_quality": "bloody"},
                )
                for index in range(1, 15)
            ]
        )
    )
    SummaryWorker().rebuild_for_pet(
        repository=repository,
        user_id="user_123",
        pet_id="dog_mochi",
    )

    snapshot = repository.get_context_snapshot(user_id="user_123", pet_id="dog_mochi")

    assert snapshot.pet_profile["name"] == "Mochi"
    assert "bloody stool" in snapshot.active_issues
    assert len(snapshot.recent_trends) <= 2
    assert len(snapshot.important_historical_flags) == 14
