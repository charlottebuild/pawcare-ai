from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pawcare.schemas.state import Observation, ObservationCategory
from pawcare.services.pet_models import CareRoutine, MonitoringAlert, PetRecord
from pawcare.services.pet_repository import PetRecordAccessError
from pawcare.skills.symptom_understanding import contains_any
from pawcare.storage.sqlite_pet_repository import SQLitePetRepository


@dataclass(frozen=True)
class MonitoringScanReport:
    db_path: str
    scanned_at: str
    pets_scanned: int
    routines_checked: int
    observations_checked: int
    alerts: list[MonitoringAlert]
    duration_ms: float

    @property
    def alerts_generated(self) -> int:
        return len(self.alerts)

    @property
    def high_risk_alerts_generated(self) -> int:
        return len(
            [
                alert
                for alert in self.alerts
                if alert.alert_type == "observation_risk" and alert.severity == "high"
            ]
        )

    @property
    def routine_alerts_generated(self) -> int:
        return len([alert for alert in self.alerts if alert.alert_type == "routine_due"])

    @property
    def red_flag_domains(self) -> list[str]:
        domains = {
            alert.source.removeprefix("observation:").split(":", 1)[0]
            for alert in self.alerts
            if alert.source.startswith("observation:")
        }
        return sorted(domain for domain in domains if domain)

    def as_dict(self) -> dict[str, object]:
        return {
            "db_path": self.db_path,
            "scanned_at": self.scanned_at,
            "pets_scanned": self.pets_scanned,
            "routines_checked": self.routines_checked,
            "observations_checked": self.observations_checked,
            "alerts_generated": self.alerts_generated,
            "high_risk_alerts_generated": self.high_risk_alerts_generated,
            "routine_alerts_generated": self.routine_alerts_generated,
            "red_flag_domains": self.red_flag_domains,
            "duration_ms": self.duration_ms,
            "alerts": [asdict(alert) for alert in self.alerts],
        }

    def format(self) -> str:
        lines = [
            "PawCare local monitoring scan",
            f"Database: {self.db_path}",
            f"Scanned at: {self.scanned_at}",
            f"Pets scanned: {self.pets_scanned}",
            f"Routines checked: {self.routines_checked}",
            f"Observations checked: {self.observations_checked}",
            f"Alerts generated: {self.alerts_generated}",
            f"High-risk observation alerts: {self.high_risk_alerts_generated}",
            f"Routine alerts: {self.routine_alerts_generated}",
            "Red-flag domains: "
            + (", ".join(self.red_flag_domains) if self.red_flag_domains else "none"),
            f"Duration: {self.duration_ms:.3f}ms",
        ]
        for alert in self.alerts:
            lines.append(
                f"- [{alert.severity}] {alert.user_id}/{alert.pet_id}: "
                f"{alert.reason} ({alert.source})"
            )
        return "\n".join(lines)


class MonitoringWorker:
    """Local abnormal-signal scanner for SQLite-backed PawCare workspaces."""

    def scan(
        self,
        *,
        repository: SQLitePetRepository,
        db_path: str | Path,
        now: datetime | None = None,
        user_id: str | None = None,
        pet_id: str | None = None,
        lookback_hours: int = 24,
    ) -> MonitoringScanReport:
        if pet_id and not user_id:
            raise ValueError("--pet-id requires --user-id")

        started = time.perf_counter()
        scan_time = now or datetime.now(UTC)
        pets = self._select_pets(repository=repository, user_id=user_id, pet_id=pet_id)
        alerts: list[MonitoringAlert] = []
        routines_checked = 0
        observations_checked = 0

        for pet in pets:
            routines = repository.list_care_routines(
                user_id=pet.user_id,
                pet_id=pet.pet_id,
            )
            routines_checked += len(routines)
            alerts.extend(
                self._routine_alerts(pet=pet, routines=routines, now=scan_time)
            )
            recent_observations = self._recent_observations(
                observations=pet.observations,
                now=scan_time,
                lookback_hours=lookback_hours,
            )
            observations_checked += len(recent_observations)
            alerts.extend(
                self._observation_alerts(
                    pet=pet,
                    observations=recent_observations,
                    now=scan_time,
                )
            )

        return MonitoringScanReport(
            db_path=str(Path(db_path)),
            scanned_at=scan_time.isoformat(),
            pets_scanned=len(pets),
            routines_checked=routines_checked,
            observations_checked=observations_checked,
            alerts=alerts,
            duration_ms=round((time.perf_counter() - started) * 1000, 3),
        )

    def _select_pets(
        self,
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

    def _routine_alerts(
        self, *, pet: PetRecord, routines: list[CareRoutine], now: datetime
    ) -> list[MonitoringAlert]:
        alerts: list[MonitoringAlert] = []
        for routine in routines:
            if not routine.enabled or not self._routine_due(routine=routine, now=now):
                continue
            alerts.append(
                self._alert(
                    pet=pet,
                    alert_type="routine_due",
                    severity="low",
                    reason=f"{routine.label} is due.",
                    recommended_next_step="Complete or reschedule this care routine.",
                    source=f"routine:{routine.routine_id}",
                    now=now,
                )
            )
        return alerts

    def _routine_due(self, *, routine: CareRoutine, now: datetime) -> bool:
        if routine.schedule_kind == "daily" and routine.time_of_day:
            try:
                hour, minute = [int(part) for part in routine.time_of_day.split(":", 1)]
            except ValueError:
                return False
            due_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return timedelta(minutes=0) <= now - due_at <= timedelta(hours=1)
        if routine.schedule_kind == "interval" and routine.interval_hours:
            if routine.interval_hours <= 0:
                return False
            elapsed_hours = now.hour + (now.minute / 60)
            remainder = elapsed_hours % routine.interval_hours
            return remainder <= 0.25 or routine.interval_hours - remainder <= 0.25
        return False

    def _recent_observations(
        self, *, observations: list[Observation], now: datetime, lookback_hours: int
    ) -> list[Observation]:
        cutoff = now - timedelta(hours=lookback_hours)
        recent: list[Observation] = []
        for observation in observations:
            timestamp = _parse_timestamp(observation.timestamp)
            if timestamp is not None and cutoff <= timestamp <= now:
                recent.append(observation)
        return recent

    def _observation_alerts(
        self, *, pet: PetRecord, observations: list[Observation], now: datetime
    ) -> list[MonitoringAlert]:
        alerts: list[MonitoringAlert] = []
        for observation in observations:
            signal = self._high_risk_signal(observation)
            if signal is None:
                continue
            domain, reason = signal
            alerts.append(
                self._alert(
                    pet=pet,
                    alert_type="observation_risk",
                    severity="high",
                    reason=reason,
                    recommended_next_step=(
                        "Review this update and contact a veterinarian urgently if the "
                        "sign is ongoing or worsening."
                    ),
                    source=f"observation:{domain}:{observation.observation_id}",
                    now=now,
                )
            )
        return alerts

    def _high_risk_signal(self, observation: Observation) -> tuple[str, str] | None:
        context = observation.health_context or {}
        raw_text = observation.raw_text
        if context.get("urinary_obstruction"):
            return "urinary", "Urinary red flag was recorded."
        if context.get("respiratory_distress"):
            return "respiratory", "Respiratory distress red flag was recorded."
        if observation.category == ObservationCategory.stool and context.get(
            "stool_quality"
        ) in {"bloody", "black_tarry"}:
            return "gi", "Blood or black/tarry stool was recorded."
        if observation.category == ObservationCategory.vomiting and context.get(
            "vomiting_reported"
        ):
            return "gi", "Vomiting was recorded and should be monitored for repetition or worsening."
        if observation.category == ObservationCategory.mobility and (
            context.get("weight_bearing") == "non_weight_bearing"
            or context.get("post_op_context")
        ):
            return "mobility", "Post-op or non-weight-bearing mobility concern was recorded."
        if contains_any(raw_text, ["seizure", "convulsion", "shaking uncontrollably", "抽搐"]):
            return "neurologic", "Seizure-like wording was recorded."
        if contains_any(
            raw_text,
            ["bloated", "bloat", "distended belly", "trying to vomit but nothing"],
        ):
            return "abdominal", "Abdominal distension or unproductive retching wording was recorded."
        if contains_any(
            raw_text,
            ["eye injury", "hurt eye", "eye trauma", "eye scratch", "eye popped out"],
        ):
            return "eye", "Eye injury red flag wording was recorded."
        return None

    def _alert(
        self,
        *,
        pet: PetRecord,
        alert_type: str,
        severity: str,
        reason: str,
        recommended_next_step: str,
        source: str,
        now: datetime,
    ) -> MonitoringAlert:
        alert_id = f"{pet.user_id}_{pet.pet_id}_{alert_type}_{abs(hash((reason, source))) % 100000}"
        return MonitoringAlert(
            alert_id=alert_id,
            user_id=pet.user_id,
            pet_id=pet.pet_id,
            alert_type=alert_type,
            severity=severity,
            reason=reason,
            recommended_next_step=recommended_next_step,
            source=source,
            created_at=now.isoformat(),
        )


def run_sqlite_monitoring_scan(
    *,
    db_path: str | Path,
    user_id: str | None = None,
    pet_id: str | None = None,
    now: str | None = None,
    lookback_hours: int = 24,
) -> MonitoringScanReport:
    repository = SQLitePetRepository(db_path)
    return MonitoringWorker().scan(
        repository=repository,
        db_path=db_path,
        now=_parse_timestamp(now) if now else None,
        user_id=user_id,
        pet_id=pet_id,
        lookback_hours=lookback_hours,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run PawCare local abnormal-signal monitoring scan."
    )
    parser.add_argument("--db", required=True, help="Path to PawCare SQLite database.")
    parser.add_argument("--user-id", default=None, help="Optional user id filter.")
    parser.add_argument("--pet-id", default=None, help="Optional pet id filter.")
    parser.add_argument("--now", default=None, help="Optional ISO timestamp for tests.")
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument("--watch", action="store_true", help="Run continuously.")
    parser.add_argument("--interval-seconds", type=float, default=60)
    parser.add_argument("--report-json", default=None)
    args = parser.parse_args()

    try:
        if args.watch:
            while True:
                report = run_sqlite_monitoring_scan(
                    db_path=args.db,
                    user_id=args.user_id,
                    pet_id=args.pet_id,
                    now=args.now,
                    lookback_hours=args.lookback_hours,
                )
                _emit_report(report=report, report_json=args.report_json)
                time.sleep(args.interval_seconds)
        report = run_sqlite_monitoring_scan(
            db_path=args.db,
            user_id=args.user_id,
            pet_id=args.pet_id,
            now=args.now,
            lookback_hours=args.lookback_hours,
        )
    except (ValueError, PetRecordAccessError) as exc:
        parser.error(str(exc))
    _emit_report(report=report, report_json=args.report_json)


def _emit_report(*, report: MonitoringScanReport, report_json: str | None) -> None:
    if report_json:
        Path(report_json).write_text(
            json.dumps(report.as_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    print(report.format())


def _parse_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


if __name__ == "__main__":
    main()
