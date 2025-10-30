import pytest
from src.domain.value_objects.volume import Volume, VolumeQuality


def test_volume_validation_and_ratio():
    with pytest.raises(ValueError):
        Volume(-1, 100)

    v = Volume(2000, 1000)
    assert v.get_ratio() == 2.0
    assert v.is_strong() is True
    assert v.is_sufficient(1.2) is True
    assert v.is_weak() is False


def test_volume_quality():
    assert Volume(1500, 1000).get_quality() == VolumeQuality.EXCELLENT  # >=1.5x is EXCELLENT
    assert Volume(1600, 1000).get_quality() == VolumeQuality.EXCELLENT
    assert Volume(600, 1000).get_quality() == VolumeQuality.FAIR
    assert Volume(500, 1000).get_quality() == VolumeQuality.LOW


def test_volume_format_suffix():
    assert Volume(999).format_with_suffix() == "999"
    assert Volume(12_345).format_with_suffix().endswith("K")
    assert Volume(12_345_678).format_with_suffix().endswith("M")
