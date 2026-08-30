from datetime import datetime, timedelta, timezone

import pytest

from app.domain.data.service.LttbDownsampler import lttb_downsample


def _points(count: int) -> list[tuple[datetime, float]]:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    return [
        (start + timedelta(seconds=index), float((index * index) % 37))
        for index in range(count)
    ]


@pytest.mark.parametrize("raw_count", [0, 99, 100])
def test_lttb_returns_all_points_at_or_below_threshold(raw_count: int) -> None:
    points = _points(raw_count)

    assert lttb_downsample(iter(points), raw_count, 100) == points


def test_lttb_returns_exact_threshold_and_preserves_endpoints() -> None:
    points = _points(250)

    result = lttb_downsample(iter(points), len(points), 100)

    assert len(result) == 100
    assert result[0] == points[0]
    assert result[-1] == points[-1]
    assert [item[0] for item in result] == sorted(item[0] for item in result)


def test_lttb_is_deterministic() -> None:
    points = _points(250)

    first = lttb_downsample(iter(points), len(points), 100)
    second = lttb_downsample(iter(points), len(points), 100)

    assert first == second
