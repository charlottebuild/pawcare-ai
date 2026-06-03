from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from pawcare.services import PetRecord, SummaryWorker
from pawcare.storage.sqlite_pet_repository import SQLitePetRepository


@dataclass(frozen=True)
class SummaryRebuildReport:
    db_path: str
    dry_run: bool
    pets_processed: int
    observations_seen: int
    daily_summaries: int
    weekly_summaries: int
    monthly_summaries: int
    pet_keys: list[str]

    def format(self) -> str:
        action = "Would rebuild" if self.dry_run else "Rebuilt"
        lines = [
            f"{action} PawCare pet memory summaries",
            f"Database: {self.db_path}",
            f"Pets: {self.pets_processed}",
            f"Observations: {self.observations_seen}",
            (
                "Summaries: "
                f"daily={self.daily_summaries}, "
                f"weekly={self.weekly_summaries}, "
                f"monthly={self.monthly_summaries}"
            ),
        ]
        if self.pet_keys:
            lines.append("Pet keys: " + ", ".join(self.pet_keys))
        return "\n".join(lines)


def rebuild_sqlite_pet_memory(
    *,
    db_path: str | Path,
    user_id: str | None = None,
    pet_id: str | None = None,
    dry_run: bool = False,
) -> SummaryRebuildReport:
    if pet_id and not user_id:
        raise ValueError("--pet-id requires --user-id")

    repository = SQLitePetRepository(db_path)
    worker = SummaryWorker()
    pets = _select_pets(repository=repository, user_id=user_id, pet_id=pet_id)
    observations_seen = 0
    daily_count = 0
    weekly_count = 0
    monthly_count = 0

    for pet in pets:
        daily = worker.build_daily_summaries(pet=pet)
        weekly = worker.build_weekly_summaries(pet=pet)
        monthly = worker.build_monthly_summaries(pet=pet)
        observations_seen += len(pet.observations)
        daily_count += len(daily)
        weekly_count += len(weekly)
        monthly_count += len(monthly)
        if dry_run:
            continue
        repository.save_daily_summaries(
            user_id=pet.user_id,
            pet_id=pet.pet_id,
            summaries=daily,
        )
        repository.save_weekly_summaries(
            user_id=pet.user_id,
            pet_id=pet.pet_id,
            summaries=weekly,
        )
        repository.save_monthly_summaries(
            user_id=pet.user_id,
            pet_id=pet.pet_id,
            summaries=monthly,
        )

    return SummaryRebuildReport(
        db_path=str(Path(db_path)),
        dry_run=dry_run,
        pets_processed=len(pets),
        observations_seen=observations_seen,
        daily_summaries=daily_count,
        weekly_summaries=weekly_count,
        monthly_summaries=monthly_count,
        pet_keys=[f"{pet.user_id}/{pet.pet_id}" for pet in pets],
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebuild PawCare SQLite pet memory summaries."
    )
    parser.add_argument("--db", required=True, help="Path to PawCare SQLite database.")
    parser.add_argument("--user-id", default=None, help="Optional user id filter.")
    parser.add_argument(
        "--pet-id",
        default=None,
        help="Optional pet id filter. Requires --user-id.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report selected pets and projected summary counts without writing.",
    )
    args = parser.parse_args()
    try:
        report = rebuild_sqlite_pet_memory(
            db_path=args.db,
            user_id=args.user_id,
            pet_id=args.pet_id,
            dry_run=args.dry_run,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(report.format())


def _select_pets(
    *,
    repository: SQLitePetRepository,
    user_id: str | None,
    pet_id: str | None,
) -> list[PetRecord]:
    if user_id and pet_id:
        return [repository.get_pet(user_id=user_id, pet_id=pet_id)]
    if user_id:
        return repository.list_pets(user_id=user_id)
    pets: list[PetRecord] = []
    for current_user_id in repository.list_user_ids():
        pets.extend(repository.list_pets(user_id=current_user_id))
    return pets


if __name__ == "__main__":
    main()
