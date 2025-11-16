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
