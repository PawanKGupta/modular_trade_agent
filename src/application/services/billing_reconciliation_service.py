"""Billing reconciliation: performance-fee overdue marking."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.application.services.performance_billing_service import PerformanceBillingService


class BillingReconciliationService:
    def __init__(self, db: Session):
        self.db = db

    def run(self) -> dict[str, Any]:
        perf_overdue = PerformanceBillingService(self.db).mark_overdue_bills()
        return {"performance_bills_marked_overdue": perf_overdue}
