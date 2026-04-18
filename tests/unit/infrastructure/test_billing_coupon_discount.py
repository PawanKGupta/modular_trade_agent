from types import SimpleNamespace

from src.infrastructure.db.models import CouponDiscountType
from src.infrastructure.persistence.billing_repository import apply_coupon_discount


def test_percent_coupon():
    c = SimpleNamespace(discount_type=CouponDiscountType.PERCENT, discount_value=20)
    assert apply_coupon_discount(1000, c) == 800


def test_fixed_coupon():
    c = SimpleNamespace(discount_type=CouponDiscountType.FIXED, discount_value=150)
    assert apply_coupon_discount(1000, c) == 850
