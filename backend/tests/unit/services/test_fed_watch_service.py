"""FedWatch 派生聚合服务单测：hike/hold/cut 纯求和口径 + 概率和校验。"""

from datetime import date
from decimal import Decimal

import pytest

from app.models.fed_watch import FedWatchProbability
from app.services.market.fed_watch_service import derive_meetings


def _prob(meeting_date: date, low: int, high: int, p: float) -> FedWatchProbability:
    return FedWatchProbability(
        as_of_date=date(2026, 9, 7),
        meeting_date=meeting_date,
        range_low=low,
        range_high=high,
        probability=Decimal(str(p)),
    )


@pytest.mark.unit
class TestDeriveMeetings:
    def test_hike_hold_cut_sums_against_current_range(self) -> None:
        """9/16：39.6 hold + 60.4 hike（实测口径），当前区间 350-375。"""
        rows = [
            _prob(date(2026, 9, 16), 325, 350, 0.0),
            _prob(date(2026, 9, 16), 350, 375, 39.6),
            _prob(date(2026, 9, 16), 375, 400, 60.4),
            _prob(date(2026, 9, 16), 400, 425, 0.0),
        ]
        meetings = derive_meetings(rows, current_low=350, current_high=375)

        assert len(meetings) == 1
        meeting = meetings[0]
        assert meeting.meeting_date == date(2026, 9, 16)
        assert meeting.prob_hike == pytest.approx(60.4)
        assert meeting.prob_hold == pytest.approx(39.6)
        assert meeting.prob_cut == pytest.approx(0.0)
        assert (meeting.likely_range_low, meeting.likely_range_high) == (375, 400)

    def test_cut_sums_ranges_below_current(self) -> None:
        """假设当前区间已降至 325-350：350-375 计入 hike 之外的 cut 需按 low/high 判。"""
        rows = [
            _prob(date(2026, 10, 28), 300, 325, 5.0),
            _prob(date(2026, 10, 28), 325, 350, 50.0),
            _prob(date(2026, 10, 28), 350, 375, 45.0),
        ]
        meetings = derive_meetings(rows, current_low=325, current_high=350)

        assert meetings[0].prob_cut == pytest.approx(5.0)
        assert meetings[0].prob_hold == pytest.approx(50.0)
        assert meetings[0].prob_hike == pytest.approx(45.0)

    def test_meetings_sorted_and_triple_sums_to_100(self) -> None:
        rows = [
            _prob(date(2027, 1, 27), 375, 400, 35.1),
            _prob(date(2027, 1, 27), 350, 375, 10.8),
            _prob(date(2027, 1, 27), 400, 425, 37.2),
            _prob(date(2027, 1, 27), 425, 450, 14.8),
            _prob(date(2027, 1, 27), 450, 475, 2.0),
            _prob(date(2026, 12, 9), 400, 425, 35.8),
            _prob(date(2026, 12, 9), 375, 400, 41.7),
            _prob(date(2026, 12, 9), 350, 375, 14.3),
            _prob(date(2026, 12, 9), 425, 450, 8.2),
        ]
        meetings = derive_meetings(rows, current_low=350, current_high=375)

        assert [m.meeting_date for m in meetings] == [
            date(2026, 12, 9),
            date(2027, 1, 27),
        ]
        for meeting in meetings:
            assert meeting.prob_hike + meeting.prob_hold + meeting.prob_cut == (
                pytest.approx(100.0, abs=0.5)
            )

    def test_meeting_with_abnormal_sum_skipped(self) -> None:
        rows = [
            _prob(date(2026, 9, 16), 350, 375, 60.0),
            _prob(date(2026, 9, 16), 375, 400, 20.0),
            _prob(date(2026, 10, 28), 350, 375, 29.1),
            _prob(date(2026, 10, 28), 375, 400, 54.9),
            _prob(date(2026, 10, 28), 400, 425, 16.1),
        ]
        meetings = derive_meetings(rows, current_low=350, current_high=375)

        assert [m.meeting_date for m in meetings] == [date(2026, 10, 28)]
