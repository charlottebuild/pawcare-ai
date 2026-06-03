from __future__ import annotations

import pytest

from pawcare.memory.summary_worker import rebuild_sqlite_pet_memory
from pawcare.schemas.state import BehavioralBaseline, DogProfile, HealthBaseline, Observation
from pawcare.services import PetRecord, SQLitePetRepository, UserAccount


def _pet_record(*, user_id: str, pet_id: str, name: str) -> PetRecord:
    return PetRecord(
        pet_id=pet_id,
        user_id=user_id,
        dog_profile=DogProfile(id=pet_id, name=name, species="dog"),
        behavioral_baseline=BehavioralBaseline(),
        health_baseline=HealthBaseline(normal_appetite="high"),
    )


def _observation(*, observation_id: str, timestamp: str, raw_text: str) -> Observation:
    return Observation.model_validate(
        {
            "observation_id": observation_id,
            "timestamp": timestamp,
            "source": "user_log",
            "category": "stool",
            "raw_text": raw_text,
            "confidence": 0.9,
            "health_context": {"stool_quality": "bloody"},
        }
    )


def _seed_pet_with_observations(
    repository: SQLitePetRepository,
    *,
    user_id: str,
    pet_id: str,
    name: str,
    timestamps: list[str],
) -> None:
    repository.create_pet(_pet_record(user_id=user_id, pet_id=pet_id, name=name))
    repository.append_observations(
        user_id=user_id,
        pet_id=pet_id,
        observations=[
            _observation(
                observation_id=f"{pet_id}_obs_{index}",
                timestamp=timestamp,
                raw_text=f"{name} had bloody stool.",
            )
            for index, timestamp in enumerate(timestamps, start=1)
        ],
    )


def test_summary_worker_cli_rebuilds_all_sqlite_pets(tmp_path) -> None:
    db_path = tmp_path / "pawcare.sqlite3"
    repository = SQLitePetRepository(db_path)
    _seed_pet_with_observations(
        repository,
        user_id="user_123",
        pet_id="dog_mochi",
        name="Mochi",
        timestamps=[
            "2026-05-08T08:00:00-07:00",
            "2026-05-09T08:00:00-07:00",
        ],
    )
    _seed_pet_with_observations(
        repository,
        user_id="user_456",
        pet_id="dog_luna",
        name="Luna",
        timestamps=["2026-05-10T08:00:00-07:00"],
    )

    report = rebuild_sqlite_pet_memory(db_path=db_path)

    assert report.pets_processed == 2
    assert report.observations_seen == 3
    assert report.daily_summaries == 3
    assert report.weekly_summaries == 2
    assert report.monthly_summaries == 2
    reopened = SQLitePetRepository(db_path)
    assert len(reopened.get_daily_summaries(user_id="user_123", pet_id="dog_mochi")) == 2
    assert len(reopened.get_daily_summaries(user_id="user_456", pet_id="dog_luna")) == 1
    assert "user_123/dog_mochi" in report.format()


def test_summary_worker_cli_filters_by_user_id(tmp_path) -> None:
    db_path = tmp_path / "pawcare.sqlite3"
    repository = SQLitePetRepository(db_path)
    _seed_pet_with_observations(
        repository,
        user_id="user_123",
        pet_id="dog_mochi",
        name="Mochi",
        timestamps=["2026-05-08T08:00:00-07:00"],
    )
    _seed_pet_with_observations(
        repository,
        user_id="user_456",
        pet_id="dog_luna",
        name="Luna",
        timestamps=["2026-05-08T08:00:00-07:00"],
    )

    report = rebuild_sqlite_pet_memory(db_path=db_path, user_id="user_123")

    assert report.pet_keys == ["user_123/dog_mochi"]
    reopened = SQLitePetRepository(db_path)
    assert len(reopened.get_daily_summaries(user_id="user_123", pet_id="dog_mochi")) == 1
    assert len(reopened.get_daily_summaries(user_id="user_456", pet_id="dog_luna")) == 0


def test_summary_worker_cli_filters_by_user_and_pet_id(tmp_path) -> None:
    db_path = tmp_path / "pawcare.sqlite3"
    repository = SQLitePetRepository(db_path)
    _seed_pet_with_observations(
        repository,
        user_id="user_123",
        pet_id="dog_mochi",
        name="Mochi",
        timestamps=["2026-05-08T08:00:00-07:00"],
    )
    _seed_pet_with_observations(
        repository,
        user_id="user_123",
        pet_id="dog_bear",
        name="Bear",
        timestamps=["2026-05-08T08:00:00-07:00"],
    )

    report = rebuild_sqlite_pet_memory(
        db_path=db_path,
        user_id="user_123",
        pet_id="dog_bear",
    )

    assert report.pet_keys == ["user_123/dog_bear"]
    reopened = SQLitePetRepository(db_path)
    assert len(reopened.get_daily_summaries(user_id="user_123", pet_id="dog_bear")) == 1
    assert len(reopened.get_daily_summaries(user_id="user_123", pet_id="dog_mochi")) == 0


def test_summary_worker_cli_dry_run_does_not_write_summaries(tmp_path) -> None:
    db_path = tmp_path / "pawcare.sqlite3"
    repository = SQLitePetRepository(db_path)
    _seed_pet_with_observations(
        repository,
        user_id="user_123",
        pet_id="dog_mochi",
        name="Mochi",
        timestamps=["2026-05-08T08:00:00-07:00"],
    )

    report = rebuild_sqlite_pet_memory(db_path=db_path, dry_run=True)

    assert report.dry_run is True
    assert report.daily_summaries == 1
    assert "Would rebuild" in report.format()
    reopened = SQLitePetRepository(db_path)
    assert len(reopened.get_daily_summaries(user_id="user_123", pet_id="dog_mochi")) == 0


def test_summary_worker_cli_handles_empty_database_and_empty_observations(tmp_path) -> None:
    db_path = tmp_path / "pawcare.sqlite3"
    report = rebuild_sqlite_pet_memory(db_path=db_path)
    assert report.pets_processed == 0
    assert report.observations_seen == 0

    repository = SQLitePetRepository(db_path)
    repository.create_user(UserAccount(user_id="user_empty"))
    repository.create_pet(
        _pet_record(user_id="user_empty", pet_id="dog_empty", name="Empty")
    )

    empty_pet_report = rebuild_sqlite_pet_memory(db_path=db_path)
    assert empty_pet_report.pets_processed == 1
    assert empty_pet_report.observations_seen == 0
    assert empty_pet_report.daily_summaries == 0


def test_summary_worker_cli_requires_user_id_for_pet_filter(tmp_path) -> None:
    with pytest.raises(ValueError, match="--pet-id requires --user-id"):
        rebuild_sqlite_pet_memory(
            db_path=tmp_path / "pawcare.sqlite3",
            pet_id="dog_mochi",
        )
