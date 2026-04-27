# ruff: noqa: B008
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class TransactionOut(BaseModel):
    id: int
    user_id: int
    user_subscription_id: int | None
    amount_paise: int
    currency: str
    status: str
    razorpay_payment_id: str | None
    failure_reason: str | None
    created_at: datetime


class AdminBillingSettingsUpdate(BaseModel):
    payment_card_enabled: bool | None = None
    payment_upi_enabled: bool | None = None
    performance_fee_payment_days_after_invoice: int | None = Field(default=None, ge=0, le=90)
    performance_fee_default_percentage: float | None = Field(default=None, ge=0, le=100)


class AdminRazorpayCredentialsPatch(BaseModel):
    """Partial update. Omitted fields are unchanged. Null clears stored DB value for that field."""

    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None
    razorpay_webhook_secret: str | None = None


class AdminRefundRequest(BaseModel):
    billing_transaction_id: int
    amount_paise: int | None = Field(
        default=None,
        description="Partial refund in paise; omit for full refund (Razorpay default)",
    )
    reason: str | None = None


class PerformanceBillOut(BaseModel):
    id: int
    bill_month: date
    generated_at: datetime
    due_at: datetime
    status: str
    payable_amount: float
    fee_amount: float
    chargeable_profit: float
    current_month_pnl: float
    previous_carry_forward_loss: float
    new_carry_forward_loss: float
    fee_percentage: float
    paid_at: datetime | None = None
    razorpay_order_id: str | None = None


class PerformanceFeeCheckoutResponse(BaseModel):
    razorpay_key_id: str
    order_id: str
    amount_paise: int
    currency: str
    bill_id: int


class PerformanceFeeArrearBillOut(BaseModel):
    id: int
    bill_month: str
    due_at: str
    payable_amount: float
    status: str


class PerformanceFeeArrearsOut(BaseModel):
    """Soft gate: new broker buys / re-entries paused until past-due performance fees are paid."""

    blocks_new_broker_buys: bool
    message: str | None = None
    bills: list[PerformanceFeeArrearBillOut] = Field(default_factory=list)


class RazorpayCreateOrderRequest(BaseModel):
    amount_paise: int = Field(..., ge=100, description="Razorpay minimum is 100 paise (₹1)")
    currency: str = "INR"
    receipt: str | None = Field(default=None, max_length=40)


class RazorpayCreateOrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str
    key_id: str


class RazorpayVerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    performance_bill_id: int | None = None


class RazorpayVerifyPaymentResponse(BaseModel):
    verified: bool
    detail: str | None = None
