"""
Persist and restore unified / individual service running state across API restarts.

Snapshots are written to a JSON file on the ``/app/data`` volume (configurable) so
redeployments can auto-restore services even when DB flags were cleared or stale.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from src.infrastructure.db.models import IndividualServiceStatus, ServiceStatus, Users
from src.infrastructure.db.timezone_utils import ist_now

logger = logging.getLogger(__name__)

SNAPSHOT_VERSION = 1
DEFAULT_SNAPSHOT_PATH = Path("data/service_restore_snapshot.json")
HISTORY_DIR_NAME = "service_restore_snapshots"
MAX_HISTORY_FILES = 10


def snapshot_path() -> Path:
    """Resolved path for the latest service-restore snapshot file."""
    raw = os.getenv("SERVICE_RESTORE_SNAPSHOT_PATH", "").strip()
    return Path(raw) if raw else DEFAULT_SNAPSHOT_PATH


def _history_dir(base: Path) -> Path:
    return base.parent / HISTORY_DIR_NAME


def capture_live_unified_user_ids() -> list[int]:
    """User IDs whose unified scheduler thread is alive in this API process."""
    try:
        from src.application.services.multi_user_trading_service import _shared_service_threads

        return sorted(
            uid
            for uid, thread in _shared_service_threads.items()
            if thread is not None and thread.is_alive()
        )
    except Exception:
        return []


def capture_from_database(db: Session) -> tuple[list[int], list[tuple[int, str]]]:
    """Return (unified_user_ids, individual (user_id, task_name)) marked running in DB."""
    running_unified = db.query(ServiceStatus).filter(ServiceStatus.service_running.is_(True)).all()
    running_individual = (
        db.query(IndividualServiceStatus).filter(IndividualServiceStatus.is_running.is_(True)).all()
    )
    unified_user_ids = sorted({status.user_id for status in running_unified})
    individual_services = [(s.user_id, s.task_name) for s in running_individual]
    return unified_user_ids, individual_services


def build_snapshot(db: Session, *, source: str) -> dict[str, Any]:
    """Build a snapshot dict from DB plus in-process unified threads."""
    db_unified, db_individual = capture_from_database(db)
    live_unified = capture_live_unified_user_ids()
    unified_user_ids = sorted(set(db_unified) | set(live_unified))
    individual_services = [
        {"user_id": user_id, "task_name": task_name} for user_id, task_name in db_individual
    ]
    return {
        "version": SNAPSHOT_VERSION,
        "captured_at": ist_now().isoformat(),
        "source": source,
        "unified_user_ids": unified_user_ids,
        "individual_services": individual_services,
    }


def merge_restore_targets(
    *payloads: dict[str, Any] | None,
) -> tuple[list[int], list[tuple[int, str]]]:
    """Union unified user IDs and individual services from multiple snapshot payloads."""
    unified: set[int] = set()
    individual: list[tuple[int, str]] = []
    seen_individual: set[tuple[int, str]] = set()

    for payload in payloads:
        if not payload:
            continue
        for uid in payload.get("unified_user_ids") or []:
            try:
                unified.add(int(uid))
            except (TypeError, ValueError):
                continue
        for item in payload.get("individual_services") or []:
            if not isinstance(item, dict):
                continue
            try:
                key = (int(item["user_id"]), str(item["task_name"]))
            except (KeyError, TypeError, ValueError):
                continue
            if key not in seen_individual:
                seen_individual.add(key)
                individual.append(key)

    return sorted(unified), individual


def save_snapshot(snapshot: dict[str, Any], path: Path | None = None) -> Path:
    """Write snapshot JSON atomically; keep a short rolling history."""
    target = path or snapshot_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(target)

    history_dir = _history_dir(target)
    history_dir.mkdir(parents=True, exist_ok=True)
    stamp = ist_now().strftime("%Y%m%d_%H%M%S")
    history_file = history_dir / f"snapshot_{stamp}.json"
    history_file.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    history_files = sorted(history_dir.glob("snapshot_*.json"), reverse=True)
    for old in history_files[MAX_HISTORY_FILES:]:
        with contextlib.suppress(OSError):
            old.unlink()

    return target


def load_snapshot(path: Path | None = None) -> dict[str, Any] | None:
    """Load the latest snapshot file, or None if missing/invalid."""
    target = path or snapshot_path()
    if not target.is_file():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read service restore snapshot %s: %s", target, exc)
        return None
    if not isinstance(data, dict):
        return None
    return data


@dataclass
class ServiceRestoreSummary:
    """Counts from a cleanup + auto-restore pass."""

    unified_marked_stopped: int = 0
    individual_marked_stopped: int = 0
    unified_restored: int = 0
    individual_restored: int = 0
    unified_failed: int = 0
    individual_failed: int = 0
    unified_skipped: int = 0
    individual_skipped: int = 0
    individual_conflict: int = 0
    snapshot_path: str | None = None
    unified_targets: list[int] = field(default_factory=list)
    individual_targets: list[tuple[int, str]] = field(default_factory=list)


def cleanup_and_restore_services(db: Session) -> ServiceRestoreSummary:
    """
    Mark orphaned DB rows stopped and auto-restore services from DB + snapshot file.

    Called once during API startup. Merges:
    - persisted snapshot (previous shutdown or pre-deploy backup)
    - current DB ``service_running`` / ``is_running`` flags
    - live in-process unified threads (empty after cold start)
    """
    summary = ServiceRestoreSummary()

    file_snapshot = load_snapshot()
    db_unified, db_individual = capture_from_database(db)
    live_unified = capture_live_unified_user_ids()
    pre_shutdown_snapshot = build_snapshot(db, source="startup_capture")

    unified_user_ids, individual_services = merge_restore_targets(
        file_snapshot,
        pre_shutdown_snapshot,
        {
            "unified_user_ids": sorted(set(db_unified) | set(live_unified)),
            "individual_services": [
                {"user_id": u, "task_name": t} for u, t in db_individual
            ],
        },
    )
    summary.unified_targets = unified_user_ids
    summary.individual_targets = individual_services

    if file_snapshot:
        print(
            f"[Startup] Loaded service restore snapshot "
            f"({file_snapshot.get('captured_at', 'unknown')}, "
            f"source={file_snapshot.get('source', '?')})"
        )

    running_unified = (
        db.query(ServiceStatus).filter(ServiceStatus.service_running.is_(True)).all()
        if unified_user_ids or db_unified
        else []
    )
    running_individual = (
        db.query(IndividualServiceStatus)
        .filter(IndividualServiceStatus.is_running.is_(True))
        .all()
        if individual_services or db_individual
        else []
    )

    if running_unified:
        print(f"[Startup] Found {len(running_unified)} orphaned unified service(s)")
        for status in running_unified:
            status.service_running = False
            print(f"[Startup] Marked unified service as stopped for user {status.user_id}")
        db.commit()
        summary.unified_marked_stopped = len(running_unified)

    if running_individual:
        print(f"[Startup] Found {len(running_individual)} orphaned individual services")
        for status in running_individual:
            status.is_running = False
            status.process_id = None
            print(f"[Startup] Marked {status.task_name} stopped for user {status.user_id}")
        db.commit()
        summary.individual_marked_stopped = len(running_individual)

    if summary.unified_marked_stopped or summary.individual_marked_stopped:
        print("[Startup] ✓ Cleaned up orphaned service status")

    if not unified_user_ids and not individual_services:
        return summary

    print(
        f"[Startup] Auto-restoring services "
        f"({len(unified_user_ids)} unified, {len(individual_services)} individual targets)..."
    )

    try:
        from src.application.services.individual_service_manager import IndividualServiceManager
        from src.application.services.multi_user_trading_service import MultiUserTradingService

        trading_service = MultiUserTradingService(db)
        individual_manager = IndividualServiceManager(db)

        for user_id in unified_user_ids:
            try:
                user = db.query(Users).filter(Users.id == user_id).first()
                if not user:
                    summary.unified_skipped += 1
                    print(f"[Startup] ⚠ Skipping auto-restore for user {user_id}: user not found")
                    continue
                if trading_service.start_service(user_id):
                    summary.unified_restored += 1
                    print(f"[Startup] ✓ Auto-restored unified service for user {user_id}")
                else:
                    summary.unified_failed += 1
                    print(
                        f"[Startup] ✗ Failed to auto-restore unified service for user {user_id}"
                    )
            except ValueError as exc:
                summary.unified_failed += 1
                print(f"[Startup] ✗ Cannot auto-restore unified service for user {user_id}: {exc}")
            except Exception as exc:
                summary.unified_failed += 1
                print(f"[Startup] ✗ Error auto-restoring unified service for user {user_id}: {exc}")
                traceback.print_exc()

        for user_id, task_name in individual_services:
            try:
                user = db.query(Users).filter(Users.id == user_id).first()
                if not user:
                    summary.individual_skipped += 1
                    print(
                        f"[Startup] ⚠ Skipping auto-restore for user {user_id}, "
                        f"task {task_name}: user not found"
                    )
                    continue
                success, message = individual_manager.start_service(user_id, task_name)
                if success:
                    summary.individual_restored += 1
                    print(f"[Startup] ✓ Auto-restored {task_name} for user {user_id}")
                elif "unified service is running" in message.lower():
                    summary.individual_conflict += 1
                    print(
                        f"[Startup] ⚠ Skipped auto-restore of {task_name} for user {user_id}: "
                        "unified service is running (conflict prevented)"
                    )
                else:
                    summary.individual_failed += 1
                    print(
                        f"[Startup] ✗ Failed to auto-restore {task_name} for user {user_id}: "
                        f"{message}"
                    )
            except FileNotFoundError:
                summary.individual_failed += 1
                print(
                    f"[Startup] ✗ Cannot auto-restore {task_name} for user {user_id}: "
                    "runner script not found"
                )
            except ValueError as exc:
                summary.individual_failed += 1
                print(
                    f"[Startup] ✗ Cannot auto-restore {task_name} for user {user_id}: {exc}"
                )
            except Exception as exc:
                summary.individual_failed += 1
                print(
                    f"[Startup] ✗ Error auto-restoring {task_name} for user {user_id}: {exc}"
                )
                traceback.print_exc()

        total_restored = summary.unified_restored + summary.individual_restored
        if total_restored > 0:
            print(
                f"[Startup] ✓ Auto-restored {total_restored} service(s) "
                f"({summary.unified_restored} unified, {summary.individual_restored} individual)"
            )
        if summary.individual_conflict > 0:
            print(
                f"[Startup] ℹ Skipped {summary.individual_conflict} individual service(s) "
                "due to unified service conflicts (expected behavior)"
            )
        if summary.unified_skipped + summary.individual_skipped > 0:
            print(
                f"[Startup] ⚠ Skipped "
                f"{summary.unified_skipped + summary.individual_skipped} service(s) "
                "(users not found)"
            )
        if summary.unified_failed + summary.individual_failed > 0:
            print(
                f"[Startup] ⚠ Failed to auto-restore "
                f"{summary.unified_failed + summary.individual_failed} service(s) — "
                "check logs; snapshot retained for retry"
            )

    except Exception as restore_error:
        print(f"[Startup] Warning: Failed to auto-restore services: {restore_error}")
        traceback.print_exc()

    try:
        post_snapshot = build_snapshot(db, source="post_restore")
        post_snapshot["restore_summary"] = {
            "unified_targets": unified_user_ids,
            "individual_targets": [
                {"user_id": u, "task_name": t} for u, t in individual_services
            ],
            "unified_restored": summary.unified_restored,
            "individual_restored": summary.individual_restored,
            "unified_failed": summary.unified_failed,
            "individual_failed": summary.individual_failed,
        }
        saved = save_snapshot(post_snapshot)
        summary.snapshot_path = str(saved)
        print(f"[Startup] Service restore snapshot updated: {saved}")
    except Exception as exc:
        logger.warning("Failed to update service restore snapshot after restore: %s", exc)

    return summary


def persist_service_restore_snapshot(db: Session, *, source: str) -> Path | None:
    """Capture current running services and write snapshot (shutdown / CLI backup)."""
    try:
        snapshot = build_snapshot(db, source=source)
        path = save_snapshot(snapshot)
        print(f"[ServiceSnapshot] Saved restore snapshot ({source}): {path}")
        return path
    except Exception as exc:
        logger.error("Failed to persist service restore snapshot: %s", exc, exc_info=True)
        return None
