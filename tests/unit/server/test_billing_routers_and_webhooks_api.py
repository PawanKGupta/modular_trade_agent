# ruff: noqa: E402, PLC0415, E501
"""API coverage for billing admin/user routers, Razorpay webhooks, and entitlement dependency."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from server.app.main import app
from src.infrastructure.db.models import (
    BillingAdminSettings,
    BillingTransactionStatus,
    MonthlyPerformanceBill,
    PerformanceBillStatus,
    UserRole,
)
from src.infrastructure.persistence.billing_repository import BillingRepository
from src.infrastructure.persistence.user_repository import UserRepository
from tests.support.test_users import create_verified_user


@pytest.fixture
def admin_user(db_session):
    return create_verified_user(
        UserRepository(db_session),
        email="billing-admin@example.com",
        password="Admin@123",
        role=UserRole.ADMIN,
    )


@pytest.fixture
def normal_user(db_session):
    return create_verified_user(
        UserRepository(db_session),
        email="billing-user@example.com",
        password="User@123",
        role=UserRole.USER,
    )


@pytest.fixture
def client(db_session):
    from server.app.core.deps import get_db

    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


class TestBillingAdminRouter:
    def test_non_admin_forbidden(self, client: TestClient, normal_user):
        token = _login(client, normal_user.email, "User@123")
        r = client.get(
            "/api/v1/admin/billing/settings",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403

    def test_get_and_patch_settings(self, client: TestClient, admin_user):
        token = _login(client, admin_user.email, "Admin@123")
        r = client.get(
            "/api/v1/admin/billing/settings",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "payment_card_enabled" in body
        assert "offline_payment_upi_id" in body
        assert "offline_payment_instructions" in body
        assert "offline_payment_qr_image_url" in body
        assert "offline_upi_id" not in body

        r2 = client.patch(
            "/api/v1/admin/billing/settings",
            headers={"Authorization": f"Bearer {token}"},
            json={"performance_fee_payment_days_after_invoice": 7},
        )
        assert r2.status_code == 200
        assert r2.json()["performance_fee_payment_days_after_invoice"] == 7

    def test_upload_and_serve_offline_payment_qr(
        self, client: TestClient, admin_user, normal_user, tmp_path, monkeypatch
    ):
        from src.application.services import billing_offline_qr_storage as storage

        monkeypatch.setattr(storage, "BILLING_DATA_DIR", tmp_path)
        admin_token = _login(client, admin_user.email, "Admin@123")
        png = b"\x89PNG\r\n\x1a\n" + b"x" * 128
        up = client.post(
            "/api/v1/admin/billing/offline-payment-qr",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("qr.png", png, "image/png")},
        )
        assert up.status_code == 200
        assert up.json()["offline_payment_qr_uploaded"] is True

        settings = client.get(
            "/api/v1/admin/billing/settings",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert settings.json()["offline_payment_qr_uploaded"] is True

        user_token = _login(client, normal_user.email, "User@123")
        opts = client.get(
            "/api/v1/user/billing/payment-options",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert opts.json()["offline_qr_uploaded"] is True
        assert opts.json()["offline_qr_image_url"] is None

        qr = client.get(
            "/api/v1/user/billing/offline-payment-qr",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert qr.status_code == 200
        assert qr.content == png

    def test_delete_offline_payment_qr(
        self, client: TestClient, admin_user, normal_user, tmp_path, monkeypatch
    ):
        from src.application.services import billing_offline_qr_storage as storage

        monkeypatch.setattr(storage, "BILLING_DATA_DIR", tmp_path)
        admin_token = _login(client, admin_user.email, "Admin@123")
        png = b"\x89PNG\r\n\x1a\n" + b"x" * 128
        up = client.post(
            "/api/v1/admin/billing/offline-payment-qr",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("qr.png", png, "image/png")},
        )
        assert up.status_code == 200

        deleted = client.delete(
            "/api/v1/admin/billing/offline-payment-qr",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert deleted.status_code == 200
        assert deleted.json()["offline_payment_qr_uploaded"] is False

        settings = client.get(
            "/api/v1/admin/billing/settings",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert settings.json()["offline_payment_qr_uploaded"] is False

        user_token = _login(client, normal_user.email, "User@123")
        qr = client.get(
            "/api/v1/user/billing/offline-payment-qr",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert qr.status_code == 404

    def test_patch_razorpay_credentials_empty(self, client: TestClient, admin_user):
        token = _login(client, admin_user.email, "Admin@123")
        r = client.patch(
            "/api/v1/admin/billing/razorpay-credentials",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        assert r.status_code == 400

    def test_patch_razorpay_credentials_encrypts_when_key_present(
        self, client: TestClient, admin_user
    ):
        token = _login(client, admin_user.email, "Admin@123")
        r = client.patch(
            "/api/v1/admin/billing/razorpay-credentials",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "razorpay_key_id": "rzp_test_1",
                "razorpay_key_secret": "secret_value",
                "razorpay_webhook_secret": "whsec_value",
            },
        )
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_admin_transactions_filters(
        self, client: TestClient, admin_user, db_session, normal_user
    ):
        token = _login(client, admin_user.email, "Admin@123")
        repo = BillingRepository(db_session)
        repo.add_transaction(
            user_id=normal_user.id,
            user_subscription_id=None,
            amount_paise=500,
            currency="INR",
            status=BillingTransactionStatus.CAPTURED,
            razorpay_payment_id="pay_ok",
        )
        repo.add_transaction(
            user_id=normal_user.id,
            user_subscription_id=None,
            amount_paise=100,
            currency="INR",
            status=BillingTransactionStatus.FAILED,
            failure_reason="x",
        )
        r = client.get(
            "/api/v1/admin/billing/transactions",
            headers={"Authorization": f"Bearer {token}"},
            params={"user_id": normal_user.id, "failed_only": True, "limit": 10},
        )
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 1
        assert rows[0]["status"] == "failed"

    @patch("server.app.routers.billing_admin.BillingReconciliationService")
    def test_admin_reconcile(self, mock_svc, client: TestClient, admin_user):
        mock_svc.return_value.run.return_value = {"ok": True, "n": 1}
        token = _login(client, admin_user.email, "Admin@123")
        r = client.post(
            "/api/v1/admin/billing/reconcile",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json() == {"ok": True, "n": 1}

    def test_admin_list_and_record_cash_payment(
        self, client: TestClient, admin_user, normal_user, db_session
    ):
        db_session.add(BillingAdminSettings(id=1))
        bill = MonthlyPerformanceBill(
            user_id=normal_user.id,
            bill_month=date(2026, 5, 1),
            generated_at=datetime(2026, 5, 31, 12, 0, 0),
            due_at=datetime(2026, 6, 15, 12, 0, 0),
            previous_carry_forward_loss=0.0,
            current_month_pnl=100.0,
            fee_percentage=10.0,
            chargeable_profit=100.0,
            fee_amount=10.0,
            new_carry_forward_loss=0.0,
            payable_amount=10.0,
            status=PerformanceBillStatus.OVERDUE,
        )
        db_session.add(bill)
        db_session.commit()
        db_session.refresh(bill)
        token = _login(client, admin_user.email, "Admin@123")

        r_list = client.get(
            "/api/v1/admin/billing/performance-bills",
            headers={"Authorization": f"Bearer {token}"},
            params={"user_id": normal_user.id},
        )
        assert r_list.status_code == 200
        rows = r_list.json()
        assert len(rows) == 1
        assert rows[0]["user_email"] == normal_user.email
        assert rows[0]["status"] == "overdue"

        r_pay = client.post(
            f"/api/v1/admin/billing/performance-bills/{bill.id}/record-cash-payment",
            headers={"Authorization": f"Bearer {token}"},
            json={"note": "Cash at desk"},
        )
        assert r_pay.status_code == 200
        body = r_pay.json()
        assert body["bill_id"] == bill.id
        assert body["amount_paise"] == 1000

        db_session.refresh(bill)
        assert bill.status == PerformanceBillStatus.PAID

        r_empty = client.get(
            "/api/v1/admin/billing/performance-bills",
            headers={"Authorization": f"Bearer {token}"},
            params={"user_id": normal_user.id},
        )
        assert r_empty.json() == []

        r_dup = client.post(
            f"/api/v1/admin/billing/performance-bills/{bill.id}/record-cash-payment",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        assert r_dup.status_code == 400

    def test_admin_refund_not_found(self, client: TestClient, admin_user):
        token = _login(client, admin_user.email, "Admin@123")
        r = client.post(
            "/api/v1/admin/billing/refunds",
            headers={"Authorization": f"Bearer {token}"},
            json={"billing_transaction_id": 99999},
        )
        assert r.status_code == 404

    def test_admin_refund_gateway_not_configured(
        self, client: TestClient, admin_user, db_session, normal_user
    ):
        repo = BillingRepository(db_session)
        tx = repo.add_transaction(
            user_id=normal_user.id,
            user_subscription_id=None,
            amount_paise=1000,
            currency="INR",
            status=BillingTransactionStatus.CAPTURED,
            razorpay_payment_id="pay_1",
        )
        token = _login(client, admin_user.email, "Admin@123")
        with patch("server.app.routers.billing_admin.get_razorpay_gateway") as m_gw:
            gw = MagicMock()
            gw.is_configured = False
            m_gw.return_value = gw
            r = client.post(
                "/api/v1/admin/billing/refunds",
                headers={"Authorization": f"Bearer {token}"},
                json={"billing_transaction_id": tx.id},
            )
        assert r.status_code == 400
        assert "not configured" in r.json()["detail"].lower()

    def test_admin_refund_create_refund_error(
        self, client: TestClient, admin_user, db_session, normal_user
    ):
        repo = BillingRepository(db_session)
        tx = repo.add_transaction(
            user_id=normal_user.id,
            user_subscription_id=None,
            amount_paise=1000,
            currency="INR",
            status=BillingTransactionStatus.CAPTURED,
            razorpay_payment_id="pay_1",
        )
        token = _login(client, admin_user.email, "Admin@123")
        with patch("server.app.routers.billing_admin.get_razorpay_gateway") as m_gw:
            gw = MagicMock()
            gw.is_configured = True
            gw.create_refund.side_effect = RuntimeError("gateway boom")
            m_gw.return_value = gw
            r = client.post(
                "/api/v1/admin/billing/refunds",
                headers={"Authorization": f"Bearer {token}"},
                json={"billing_transaction_id": tx.id},
            )
        assert r.status_code == 400

    def test_admin_refund_success(self, client: TestClient, admin_user, db_session, normal_user):
        repo = BillingRepository(db_session)
        tx = repo.add_transaction(
            user_id=normal_user.id,
            user_subscription_id=None,
            amount_paise=1000,
            currency="INR",
            status=BillingTransactionStatus.CAPTURED,
            razorpay_payment_id="pay_1",
        )
        token = _login(client, admin_user.email, "Admin@123")
        with patch("server.app.routers.billing_admin.get_razorpay_gateway") as m_gw:
            gw = MagicMock()
            gw.is_configured = True
            gw.create_refund.return_value = {"status": "processed", "id": "rfnd_1"}
            m_gw.return_value = gw
            r = client.post(
                "/api/v1/admin/billing/refunds",
                headers={"Authorization": f"Bearer {token}"},
                json={"billing_transaction_id": tx.id, "reason": "test"},
            )
        assert r.status_code == 200
        assert r.json()["ok"] is True
        db_session.refresh(tx)
        assert tx.status == BillingTransactionStatus.REFUNDED


class TestBillingUserRouter:
    def test_payment_options_offline_by_default(self, client: TestClient, normal_user):
        token = _login(client, normal_user.email, "User@123")
        r = client.get(
            "/api/v1/user/billing/payment-options",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["online_payments_enabled"] is False
        assert body["offline_qr_uploaded"] is False

    def test_checkout_forbidden_when_online_disabled(self, client: TestClient, normal_user, db_session):
        bill = MonthlyPerformanceBill(
            user_id=normal_user.id,
            bill_month=date(2026, 6, 1),
            generated_at=datetime(2026, 6, 5, 12, 0, 0),
            due_at=datetime(2026, 6, 30, 12, 0, 0),
            previous_carry_forward_loss=0.0,
            current_month_pnl=500.0,
            fee_percentage=10.0,
            chargeable_profit=200.0,
            fee_amount=20.0,
            new_carry_forward_loss=0.0,
            payable_amount=20.0,
            status=PerformanceBillStatus.PENDING_PAYMENT,
        )
        db_session.add(bill)
        db_session.commit()
        db_session.refresh(bill)
        token = _login(client, normal_user.email, "User@123")
        r = client.post(
            f"/api/v1/user/billing/performance-bills/{bill.id}/checkout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403

    def test_performance_fee_arrears_and_bills(self, client: TestClient, normal_user):
        token = _login(client, normal_user.email, "User@123")
        r = client.get(
            "/api/v1/user/billing/performance-fee-arrears",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "blocks_new_broker_buys" in body
        r2 = client.get(
            "/api/v1/user/billing/performance-bills",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 200
        assert r2.json() == []

    def test_checkout_not_configured_returns_503(self, client: TestClient, normal_user, db_session):
        bill = MonthlyPerformanceBill(
            user_id=normal_user.id,
            bill_month=date(2026, 4, 1),
            generated_at=datetime(2026, 4, 5, 12, 0, 0),
            due_at=datetime(2026, 4, 30, 12, 0, 0),
            previous_carry_forward_loss=0.0,
            current_month_pnl=1000.0,
            fee_percentage=10.0,
            chargeable_profit=500.0,
            fee_amount=50.0,
            new_carry_forward_loss=0.0,
            payable_amount=50.0,
            status=PerformanceBillStatus.PENDING_PAYMENT,
        )
        db_session.add(bill)
        db_session.commit()
        db_session.refresh(bill)
        token = _login(client, normal_user.email, "User@123")
        BillingRepository(db_session).update_admin_settings(online_payments_enabled=True)
        with patch(
            "src.application.services.performance_fee_checkout_service.get_razorpay_gateway"
        ) as m_gw:
            gw = MagicMock()
            gw.is_configured = False
            m_gw.return_value = gw
            r = client.post(
                f"/api/v1/user/billing/performance-bills/{bill.id}/checkout",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 503

    def test_checkout_success(self, client: TestClient, normal_user, db_session):
        bill = MonthlyPerformanceBill(
            user_id=normal_user.id,
            bill_month=date(2026, 5, 1),
            generated_at=datetime(2026, 5, 5, 12, 0, 0),
            due_at=datetime(2026, 5, 31, 12, 0, 0),
            previous_carry_forward_loss=0.0,
            current_month_pnl=2000.0,
            fee_percentage=10.0,
            chargeable_profit=1000.0,
            fee_amount=100.0,
            new_carry_forward_loss=0.0,
            payable_amount=100.0,
            status=PerformanceBillStatus.PENDING_PAYMENT,
        )
        db_session.add(bill)
        db_session.commit()
        db_session.refresh(bill)
        token = _login(client, normal_user.email, "User@123")
        BillingRepository(db_session).update_admin_settings(online_payments_enabled=True)
        with patch(
            "src.application.services.performance_fee_checkout_service.get_razorpay_gateway"
        ) as m_gw:
            gw = MagicMock()
            gw.is_configured = True
            gw.key_id = "rzp_test"
            gw.create_order.return_value = {"id": "order_123", "amount": 10000, "currency": "INR"}
            m_gw.return_value = gw
            r = client.post(
                f"/api/v1/user/billing/performance-bills/{bill.id}/checkout",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 200
        data = r.json()
        assert data["order_id"] == "order_123"
        assert data["bill_id"] == bill.id

    def test_razorpay_create_order_amount_too_large(self, client: TestClient, normal_user, db_session):
        BillingRepository(db_session).update_admin_settings(online_payments_enabled=True)
        token = _login(client, normal_user.email, "User@123")
        r = client.post(
            "/api/v1/user/billing/razorpay/create-order",
            headers={"Authorization": f"Bearer {token}"},
            json={"amount_paise": 10_000_00 + 1},
        )
        assert r.status_code == 400

    def test_razorpay_create_order_no_keys_503(self, client: TestClient, normal_user, db_session):
        BillingRepository(db_session).update_admin_settings(online_payments_enabled=True)
        token = _login(client, normal_user.email, "User@123")
        with (
            patch("server.app.routers.billing_user.resolve_razorpay_key_id", return_value=None),
            patch("server.app.routers.billing_user.resolve_razorpay_key_secret", return_value=None),
        ):
            r = client.post(
                "/api/v1/user/billing/razorpay/create-order",
                headers={"Authorization": f"Bearer {token}"},
                json={"amount_paise": 500},
            )
        assert r.status_code == 503

    def test_razorpay_create_order_success_and_auth_error(self, client: TestClient, normal_user, db_session):
        BillingRepository(db_session).update_admin_settings(online_payments_enabled=True)
        token = _login(client, normal_user.email, "User@123")
        with (
            patch(
                "server.app.routers.billing_user.resolve_razorpay_key_id",
                return_value="rzp_test_abc",
            ),
            patch(
                "server.app.routers.billing_user.resolve_razorpay_key_secret",
                return_value="ksec",
            ),
            patch("server.app.routers.billing_user.get_razorpay_gateway") as m_gw,
        ):
            gw = MagicMock()
            gw.create_order.return_value = {"id": "ord1", "amount": 500, "currency": "INR"}
            m_gw.return_value = gw
            r = client.post(
                "/api/v1/user/billing/razorpay/create-order",
                headers={"Authorization": f"Bearer {token}"},
                json={"amount_paise": 500, "currency": "INR", "receipt": "rcpt1"},
            )
            assert r.status_code == 200
            data = r.json()
            assert data["order_id"] == "ord1"
            assert data["razorpay_test_mode"] is True

            gw.create_order.side_effect = Exception("Authentication failed from API")
            r2 = client.post(
                "/api/v1/user/billing/razorpay/create-order",
                headers={"Authorization": f"Bearer {token}"},
                json={"amount_paise": 500},
            )
            assert r2.status_code == 401

            gw.create_order.side_effect = Exception("other failure")
            r3 = client.post(
                "/api/v1/user/billing/razorpay/create-order",
                headers={"Authorization": f"Bearer {token}"},
                json={"amount_paise": 500},
            )
            assert r3.status_code == 500

            gw.create_order.side_effect = None
            gw.create_order.return_value = {"amount": 500}
            r4 = client.post(
                "/api/v1/user/billing/razorpay/create-order",
                headers={"Authorization": f"Bearer {token}"},
                json={"amount_paise": 500},
            )
            assert r4.status_code == 500

    def test_razorpay_verify_payment_paths(self, client: TestClient, normal_user, db_session):
        BillingRepository(db_session).update_admin_settings(online_payments_enabled=True)
        token = _login(client, normal_user.email, "User@123")
        r = client.post(
            "/api/v1/user/billing/razorpay/verify-payment",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "razorpay_order_id": "",
                "razorpay_payment_id": "p",
                "razorpay_signature": "s",
            },
        )
        assert r.status_code == 400

        with patch(
            "server.app.routers.billing_user.resolve_razorpay_key_secret",
            return_value=None,
        ):
            r2 = client.post(
                "/api/v1/user/billing/razorpay/verify-payment",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "razorpay_order_id": "o1",
                    "razorpay_payment_id": "p1",
                    "razorpay_signature": "sig",
                },
            )
        assert r2.status_code == 503

        with patch(
            "server.app.routers.billing_user.resolve_razorpay_key_secret",
            return_value="secret",
        ):
            r3 = client.post(
                "/api/v1/user/billing/razorpay/verify-payment",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "razorpay_order_id": "o1",
                    "razorpay_payment_id": "p1",
                    "razorpay_signature": "wrong",
                },
            )
        assert r3.status_code == 400

        bill = MonthlyPerformanceBill(
            user_id=normal_user.id,
            bill_month=date(2026, 6, 1),
            generated_at=datetime(2026, 6, 1, 12, 0, 0),
            due_at=datetime(2026, 6, 30, 12, 0, 0),
            previous_carry_forward_loss=0.0,
            current_month_pnl=100.0,
            fee_percentage=10.0,
            chargeable_profit=50.0,
            fee_amount=5.0,
            new_carry_forward_loss=0.0,
            payable_amount=5.0,
            status=PerformanceBillStatus.PENDING_PAYMENT,
            razorpay_order_id="match_order",
        )
        db_session.add(bill)
        db_session.commit()
        db_session.refresh(bill)
        with patch(
            "server.app.routers.billing_user.resolve_razorpay_key_secret",
            return_value="secret",
        ):
            r4 = client.post(
                "/api/v1/user/billing/razorpay/verify-payment",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "razorpay_order_id": "wrong",
                    "razorpay_payment_id": "p1",
                    "razorpay_signature": "sig",
                    "performance_bill_id": bill.id,
                },
            )
        assert r4.status_code == 400

        msg = "match_order|pay_ok"
        good_sig = hmac.new(b"secret", msg.encode("utf-8"), hashlib.sha256).hexdigest()
        with patch(
            "server.app.routers.billing_user.resolve_razorpay_key_secret",
            return_value="secret",
        ):
            r5 = client.post(
                "/api/v1/user/billing/razorpay/verify-payment",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "razorpay_order_id": "match_order",
                    "razorpay_payment_id": "pay_ok",
                    "razorpay_signature": good_sig,
                    "performance_bill_id": bill.id,
                },
            )
        assert r5.status_code == 200
        assert r5.json()["verified"] is True

    def test_my_transactions(self, client: TestClient, normal_user, db_session):
        repo = BillingRepository(db_session)
        repo.add_transaction(
            user_id=normal_user.id,
            user_subscription_id=None,
            amount_paise=200,
            currency="INR",
            status=BillingTransactionStatus.CAPTURED,
        )
        token = _login(client, normal_user.email, "User@123")
        r = client.get(
            "/api/v1/user/billing/transactions",
            headers={"Authorization": f"Bearer {token}"},
            params={"limit": 5},
        )
        assert r.status_code == 200
        assert len(r.json()) >= 1


class TestBillingWebhooksRouter:
    def _sig(self, body: bytes, secret: str) -> str:
        return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    @patch(
        "server.app.routers.billing_webhooks.resolve_razorpay_webhook_secret_from_db",
        return_value="whsec",
    )
    def test_webhook_invalid_signature(self, _mock_sec, client: TestClient):
        body = b'{"id":"e1","event":"x"}'
        r = client.post(
            "/api/v1/billing/webhooks/razorpay",
            content=body,
            headers={"X-Razorpay-Signature": "bad"},
        )
        assert r.status_code == 400

    @patch(
        "server.app.routers.billing_webhooks.resolve_razorpay_webhook_secret_from_db",
        return_value="whsec",
    )
    def test_webhook_invalid_json(self, _mock_sec, client: TestClient):
        body = b"not-json"
        sig = self._sig(body, "whsec")
        r = client.post(
            "/api/v1/billing/webhooks/razorpay",
            content=body,
            headers={"X-Razorpay-Signature": sig},
        )
        assert r.status_code == 400

    @patch(
        "server.app.routers.billing_webhooks.resolve_razorpay_webhook_secret_from_db",
        return_value="whsec",
    )
    def test_webhook_missing_event_id(self, _mock_sec, client: TestClient):
        body = json.dumps({"event": "payment.captured"}).encode()
        sig = self._sig(body, "whsec")
        r = client.post(
            "/api/v1/billing/webhooks/razorpay",
            content=body,
            headers={"X-Razorpay-Signature": sig},
        )
        assert r.status_code == 400

    @patch(
        "server.app.routers.billing_webhooks.resolve_razorpay_webhook_secret_from_db",
        return_value="whsec",
    )
    def test_webhook_deduped_and_ok(self, _mock_sec, client: TestClient, db_session):
        body = json.dumps({"id": "evt_unique_1", "event": "payment.captured"}).encode()
        sig = self._sig(body, "whsec")
        with patch("server.app.routers.billing_webhooks.BillingWebhookService") as m_svc:
            m_inst = MagicMock()
            m_svc.return_value = m_inst
            r = client.post(
                "/api/v1/billing/webhooks/razorpay",
                content=body,
                headers={"X-Razorpay-Signature": sig},
            )
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        r2 = client.post(
            "/api/v1/billing/webhooks/razorpay",
            content=body,
            headers={"X-Razorpay-Signature": sig},
        )
        assert r2.status_code == 200
        assert r2.json() == {"ok": True, "deduped": True}

    @patch(
        "server.app.routers.billing_webhooks.resolve_razorpay_webhook_secret_from_db",
        return_value="whsec",
    )
    def test_webhook_process_failure_500(self, _mock_sec, client: TestClient):
        body = json.dumps({"id": "evt_fail_1", "event": "x"}).encode()
        sig = self._sig(body, "whsec")
        with patch("server.app.routers.billing_webhooks.BillingWebhookService") as m_svc:
            m_inst = MagicMock()
            m_inst.process_payload.side_effect = RuntimeError("boom")
            m_svc.return_value = m_inst
            r = client.post(
                "/api/v1/billing/webhooks/razorpay",
                content=body,
                headers={"X-Razorpay-Signature": sig},
            )
        assert r.status_code == 500


class TestRequireEntitlementDependency:
    def test_signals_blocked_without_entitlement(self, client: TestClient, normal_user):
        token = _login(client, normal_user.email, "User@123")
        with patch(
            "server.app.core.deps.SubscriptionEntitlementService.user_has_feature",
            return_value=False,
        ):
            r = client.get(
                "/api/v1/signals/buying-zone",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 403
        assert "stock_recommendations" in r.json()["detail"]
