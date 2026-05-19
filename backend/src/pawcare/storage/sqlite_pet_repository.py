from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from pawcare.schemas.state import (
    BehavioralBaseline,
    DogProfile,
    HealthBaseline,
    Observation,
)
from pawcare.services.pet_models import PetRecord, UserAccount
from pawcare.services.pet_repository import PetRecordAccessError


class SQLitePetRepository:
    """SQLite-backed product workspace store for local/friend testing."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def create_user(self, user: UserAccount) -> UserAccount:
        with self._connect() as connection:
            connection.execute(
                """
                insert into users (user_id, display_name, email)
                values (?, ?, ?)
                on conflict(user_id) do update set
                    display_name = excluded.display_name,
                    email = excluded.email
                """,
                (user.user_id, user.display_name, user.email),
            )
        return user

    def create_pet(self, pet: PetRecord) -> PetRecord:
        with self._connect() as connection:
            user_exists = connection.execute(
                "select 1 from users where user_id = ?",
                (pet.user_id,),
            ).fetchone()
            if user_exists is None:
                connection.execute(
                    "insert into users (user_id, display_name, email) values (?, ?, ?)",
                    (pet.user_id, None, None),
                )
            connection.execute(
                """
                insert into pets (
                    user_id,
                    pet_id,
                    dog_profile_json,
                    behavioral_baseline_json,
                    health_baseline_json
                )
                values (?, ?, ?, ?, ?)
                on conflict(user_id, pet_id) do update set
                    dog_profile_json = excluded.dog_profile_json,
                    behavioral_baseline_json = excluded.behavioral_baseline_json,
                    health_baseline_json = excluded.health_baseline_json
                """,
                (
                    pet.user_id,
                    pet.pet_id,
                    self._to_json(pet.dog_profile.model_dump()),
                    self._to_json(pet.behavioral_baseline.model_dump()),
                    self._to_json(pet.health_baseline.model_dump()),
                ),
            )
            connection.execute(
                "delete from observations where user_id = ? and pet_id = ?",
                (pet.user_id, pet.pet_id),
            )
            for observation in pet.observations:
                self._insert_observation(
                    connection=connection,
                    user_id=pet.user_id,
                    pet_id=pet.pet_id,
                    observation=observation,
                )
        return self.get_pet(user_id=pet.user_id, pet_id=pet.pet_id)

    def update_pet(self, pet: PetRecord) -> PetRecord:
        self.get_pet(user_id=pet.user_id, pet_id=pet.pet_id)
        with self._connect() as connection:
            connection.execute(
                """
                update pets
                set dog_profile_json = ?,
                    behavioral_baseline_json = ?,
                    health_baseline_json = ?
                where user_id = ? and pet_id = ?
                """,
                (
                    self._to_json(pet.dog_profile.model_dump()),
                    self._to_json(pet.behavioral_baseline.model_dump()),
                    self._to_json(pet.health_baseline.model_dump()),
                    pet.user_id,
                    pet.pet_id,
                ),
            )
        return self.get_pet(user_id=pet.user_id, pet_id=pet.pet_id)

    def list_pets(self, *, user_id: str) -> list[PetRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                select user_id, pet_id, dog_profile_json, behavioral_baseline_json, health_baseline_json
                from pets
                where user_id = ?
                order by rowid
                """,
                (user_id,),
            ).fetchall()
        return [self._pet_from_row(row) for row in rows]

    def get_pet(self, *, user_id: str, pet_id: str) -> PetRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                select user_id, pet_id, dog_profile_json, behavioral_baseline_json, health_baseline_json
                from pets
                where user_id = ? and pet_id = ?
                """,
                (user_id, pet_id),
            ).fetchone()
        if row is None:
            raise PetRecordAccessError("Pet record is not available.")
        return self._pet_from_row(row)

    def append_observations(
        self,
        *,
        user_id: str,
        pet_id: str,
        observations: list[Observation],
    ) -> PetRecord:
        self.get_pet(user_id=user_id, pet_id=pet_id)
        with self._connect() as connection:
            for observation in observations:
                self._insert_observation(
                    connection=connection,
                    user_id=user_id,
                    pet_id=pet_id,
                    observation=observation,
                )
        return self.get_pet(user_id=user_id, pet_id=pet_id)

    def _initialize_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                create table if not exists users (
                    user_id text primary key,
                    display_name text,
                    email text
                );

                create table if not exists pets (
                    user_id text not null,
                    pet_id text not null,
                    dog_profile_json text not null,
                    behavioral_baseline_json text not null,
                    health_baseline_json text not null,
                    primary key (user_id, pet_id),
                    foreign key (user_id) references users(user_id)
                );

                create table if not exists observations (
                    observation_order integer primary key autoincrement,
                    user_id text not null,
                    pet_id text not null,
                    observation_json text not null,
                    foreign key (user_id, pet_id) references pets(user_id, pet_id)
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("pragma foreign_keys = on")
        return connection

    def _pet_from_row(self, row: sqlite3.Row) -> PetRecord:
        user_id = str(row["user_id"])
        pet_id = str(row["pet_id"])
        observations = self._observations_for_pet(user_id=user_id, pet_id=pet_id)
        return PetRecord(
            user_id=user_id,
            pet_id=pet_id,
            dog_profile=DogProfile.model_validate(
                json.loads(str(row["dog_profile_json"]))
            ),
            behavioral_baseline=BehavioralBaseline.model_validate(
                json.loads(str(row["behavioral_baseline_json"]))
            ),
            health_baseline=HealthBaseline.model_validate(
                json.loads(str(row["health_baseline_json"]))
            ),
            observations=observations,
        )

    def _observations_for_pet(self, *, user_id: str, pet_id: str) -> list[Observation]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                select observation_json
                from observations
                where user_id = ? and pet_id = ?
                order by observation_order
                """,
                (user_id, pet_id),
            ).fetchall()
        return [
            Observation.model_validate(json.loads(str(row["observation_json"])))
            for row in rows
        ]

    def _insert_observation(
        self,
        *,
        connection: sqlite3.Connection,
        user_id: str,
        pet_id: str,
        observation: Observation,
    ) -> None:
        connection.execute(
            """
            insert into observations (user_id, pet_id, observation_json)
            values (?, ?, ?)
            """,
            (
                user_id,
                pet_id,
                self._to_json(observation.model_dump()),
            ),
        )

    def _to_json(self, value: dict[str, Any]) -> str:
        return json.dumps(value, sort_keys=True)
