from decimal import Decimal

import pytest

from src.application.services.performance_fee_invoice_calculator import (
    compute_performance_fee_invoice,
)


def test_case_1_spec_example():
    out = compute_performance_fee_invoice(2000, 3000, 10)
    assert out["chargeable_profit"] == 1000.0
    assert out["fee_amount"] == 100.0
    assert out["new_carry_forward_loss"] == 0.0
    assert out["payable_amount"] == 100.0
    assert out["current_month_pnl"] == 3000.0
    assert out["previous_carry_forward_loss"] == 2000.0


def test_case_2_spec_example():
    out = compute_performance_fee_invoice(2000, -1000, 10)
    assert out["chargeable_profit"] == 0.0
    assert out["fee_amount"] == 0.0
    assert out["new_carry_forward_loss"] == 3000.0
    assert out["payable_amount"] == 0.0


def test_case_3_spec_example():
    out = compute_performance_fee_invoice(0, 5000, 10)
    assert out["chargeable_profit"] == 5000.0
    assert out["fee_amount"] == 500.0
    assert out["new_carry_forward_loss"] == 0.0
    assert out["payable_amount"] == 500.0


def test_profit_exactly_offsets_carry():
    out = compute_performance_fee_invoice(2000, 2000, 10)
    assert out["chargeable_profit"] == 0.0
    assert out["fee_amount"] == 0.0
    assert out["new_carry_forward_loss"] == 0.0


def test_profit_partially_offsets_carry():
    out = compute_performance_fee_invoice(2000, 1500, 10)
    assert out["chargeable_profit"] == 0.0
    assert out["fee_amount"] == 0.0
    assert out["new_carry_forward_loss"] == 500.0


def test_loss_month_no_previous_carry():
    out = compute_performance_fee_invoice(0, -500, 10)
    assert out["chargeable_profit"] == 0.0
    assert out["fee_amount"] == 0.0
    assert out["new_carry_forward_loss"] == 500.0


def test_fee_half_percent():
    out = compute_performance_fee_invoice(0, 10_000, 0.5)
    assert out["fee_amount"] == 50.0
    assert out["payable_amount"] == 50.0


def test_negative_previous_carry_clamped():
    out = compute_performance_fee_invoice(-100, 1000, 10)
    assert out["previous_carry_forward_loss"] == 0.0
    assert out["chargeable_profit"] == 1000.0
    assert out["fee_amount"] == 100.0


def test_decimal_inputs():
    out = compute_performance_fee_invoice(Decimal("2000"), Decimal("3000"), Decimal("10"))
    assert out["fee_amount"] == 100.0


@pytest.mark.parametrize(
    ("prev", "cur", "fee", "expect_fee"),
    [
        (0, 0, 10, 0.0),
        (100, 0, 10, 0.0),
    ],
)
def test_zero_payable(prev, cur, fee, expect_fee):
    out = compute_performance_fee_invoice(prev, cur, fee)
    assert out["payable_amount"] == expect_fee
    assert out["fee_amount"] == expect_fee
