from datetime import date, datetime, time

from pack_helpers import BUSINESS_HOURS

from app.agent.core_tools import is_open_at


def at(hours, weekday_hhmm):
    """weekday_hhmm: (0=segunda, 'HH:MM')."""
    day = date(2026, 10, 19 + weekday_hhmm[0])  # 2026-10-19 é segunda
    hh, mm = map(int, weekday_hhmm[1].split(":"))
    return is_open_at(hours, datetime.combine(day, time(hh, mm)))


def test_open_within_simple_interval():
    assert at(BUSINESS_HOURS, (0, "18:00"))
    assert at(BUSINESS_HOURS, (0, "22:59"))
    assert not at(BUSINESS_HOURS, (0, "23:00"))
    assert not at(BUSINESS_HOURS, (0, "17:59"))


def test_interval_crossing_midnight_stays_open_after_midnight():
    hours = {"fri": [["18:00", "02:00"]]}
    assert at(hours, (4, "23:30"))  # sexta
    assert at(hours, (5, "00:30"))  # sábado de madrugada, ainda aberto
    assert at(hours, (5, "01:59"))
    assert not at(hours, (5, "02:00"))
    assert not at(hours, (4, "17:00"))


def test_end_midnight_means_until_end_of_day():
    # bug antigo: `hora_atual < 0` nunca era verdadeiro, então sexta 23:30 contava como fechado.
    assert at(BUSINESS_HOURS, (4, "23:30"))
    assert not at(BUSINESS_HOURS, (5, "00:00"))


def test_midnight_crossing_from_sunday_wraps_to_monday():
    hours = {"sun": [["20:00", "01:00"]]}
    assert at(hours, (0, "00:30"))
    assert not at(hours, (0, "01:00"))


def test_missing_day_is_closed_and_no_hours_is_unknown():
    assert not at({"mon": [["09:00", "12:00"]]}, (1, "10:00"))
    assert is_open_at(None, datetime(2026, 10, 19, 10, 0)) is None
    assert is_open_at({}, datetime(2026, 10, 19, 10, 0)) is None


def test_multiple_intervals_per_day():
    hours = {"mon": [["11:00", "14:00"], ["18:00", "23:00"]]}
    assert at(hours, (0, "12:00")) and at(hours, (0, "19:00"))
    assert not at(hours, (0, "15:00"))
