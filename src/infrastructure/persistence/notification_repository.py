"""Repository for Notification management"""

from __future__ import annotations

from typing import Literal

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Notification
from src.infrastructure.db.timezone_utils import ist_now


class NotificationRepository:
    """Repository for managing notifications"""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        user_id: int,
        type: Literal["service", "trading", "system", "error"],
        level: Literal["info", "warning", "error", "critical"],
        title: str,
        message: str,
    ) -> Notification:
        """Create a new notification"""
        try:
            notification = Notification(
                user_id=user_id,
                type=type,
                level=level,
                title=title[:255],  # Truncate to max length
                message=message[:1024],  # Truncate to max length
                read=False,
                created_at=ist_now(),
            )
            self.db.add(notification)
            self.db.commit()
            self.db.refresh(notification)
            return notification
        except Exception as e:
            # If commit fails (e.g., due to rolled back session or integrity error),
            # rollback and retry once
            error_str = str(e).lower()
            needs_retry = (
                "rolled back" in error_str
                or "transaction" in error_str
                or "integrity" in error_str
                or "unique constraint" in error_str
            )

            if needs_retry:
                try:
                    self.db.rollback()

                    # If it's a unique constraint error on ID, fix SQLite sequence
                    if "unique constraint" in error_str and "notifications.id" in error_str:
                        self._fix_sqlite_sequence()

                    # Retry the operation after rollback
                    notification = Notification(
                        user_id=user_id,
                        type=type,
                        level=level,
                        title=title[:255],
                        message=message[:1024],
                        read=False,
                        created_at=ist_now(),
                    )
                    self.db.add(notification)
                    self.db.commit()
                    self.db.refresh(notification)
                    return notification
                except Exception as retry_error:
                    # If retry also fails, rollback and re-raise
                    try:
                        self.db.rollback()
                    except Exception:
                        pass
                    raise retry_error from e
            else:
                # For other errors, rollback and re-raise
                try:
                    self.db.rollback()
                except Exception:
                    pass
                raise

    def _fix_sqlite_sequence(self) -> None:
        """Fix SQLite auto-increment sequence for notifications table"""
        try:
            from sqlalchemy import text

            # Get the current max ID from the notifications table
            max_id_result = self.db.execute(
                select(Notification.id).order_by(Notification.id.desc()).limit(1)
            ).scalar_one_or_none()

            if max_id_result is not None:
                max_id = max_id_result
                # Update sqlite_sequence to be at least max_id + 1
                # This ensures the next auto-generated ID won't conflict
                try:
                    # Update or insert into sqlite_sequence
                    # Use max_id + 1 to ensure next ID is higher than any existing ID
                    self.db.execute(
                        text(
                            "INSERT OR REPLACE INTO sqlite_sequence (name, seq) "
                            "VALUES ('notifications', :seq)"
                        ),
                        {"seq": max_id + 1}
                    )
                    self.db.commit()
                except Exception as seq_error:
                    # If sqlite_sequence doesn't exist or update fails, that's okay
                    # SQLite will handle it automatically
                    self.db.rollback()
            else:
                # No notifications exist, reset sequence to 0
                try:
                    self.db.execute(
                        text(
                            "DELETE FROM sqlite_sequence WHERE name = 'notifications'"
                        )
                    )
                    self.db.commit()
                except Exception:
                    self.db.rollback()
        except Exception:
            # If sequence fix fails, that's okay - SQLite will handle it
            try:
                self.db.rollback()
            except Exception:
                pass

    def get(self, notification_id: int) -> Notification | None:
        """Get notification by ID"""
        return self.db.get(Notification, notification_id)

    def list(
        self,
        user_id: int,
        type: str | None = None,
        level: str | None = None,
        read: bool | None = None,
        limit: int = 100,
    ) -> list[Notification]:
        """List notifications for a user with filters"""
        stmt = select(Notification).where(Notification.user_id == user_id)

        if type:
            stmt = stmt.where(Notification.type == type)
        if level:
            stmt = stmt.where(Notification.level == level)
        if read is not None:
            stmt = stmt.where(Notification.read == read)

        stmt = stmt.order_by(desc(Notification.created_at)).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_unread(self, user_id: int, limit: int = 100) -> list[Notification]:
        """Get unread notifications for a user"""
        return self.list(user_id=user_id, read=False, limit=limit)

    def mark_read(self, notification_id: int) -> Notification:
        """Mark a notification as read"""
        notification = self.get(notification_id)
        if not notification:
            raise ValueError(f"Notification {notification_id} not found")

        notification.read = True
        notification.read_at = ist_now()
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def mark_all_read(self, user_id: int) -> int:
        """Mark all notifications as read for a user"""
        stmt = select(Notification).where(
            and_(
                Notification.user_id == user_id,
                Notification.read == False,
            )
        )
        notifications = list(self.db.execute(stmt).scalars().all())
        count = len(notifications)

        for notification in notifications:
            notification.read = True
            notification.read_at = ist_now()

        self.db.commit()
        return count

    def count_unread(self, user_id: int) -> int:
        """Count unread notifications for a user"""
        stmt = select(Notification).where(
            Notification.user_id == user_id,
            Notification.read == False,
        )
        return len(list(self.db.execute(stmt).scalars().all()))

    def update_delivery_status(
        self,
        notification_id: int,
        telegram_sent: bool | None = None,
        email_sent: bool | None = None,
        in_app_delivered: bool | None = None,
    ) -> Notification:
        """Update delivery status for a notification"""
        notification = self.get(notification_id)
        if not notification:
            raise ValueError(f"Notification {notification_id} not found")

        if telegram_sent is not None:
            notification.telegram_sent = telegram_sent
        if email_sent is not None:
            notification.email_sent = email_sent
        if in_app_delivered is not None:
            notification.in_app_delivered = in_app_delivered

        self.db.commit()
        self.db.refresh(notification)
        return notification
