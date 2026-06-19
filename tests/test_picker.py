import pytest

from everydaypassion.picker import DailyPicker

ART = ["a1", "a2", "a3", "a4", "a5"]
POEMS = ["p1", "p2", "p3", "p4", "p5"]


def test_same_date_gives_same_selection():
    picker = DailyPicker()
    first = picker.pick("2026-06-19", ART, POEMS)
    second = picker.pick("2026-06-19", ART, POEMS)
    assert first == second


def test_different_dates_can_differ():
    picker = DailyPicker()
    days = {picker.pick(d, ART, POEMS).artwork_id for d in ("2026-06-19", "2026-06-20", "2026-06-21")}
    assert len(days) > 1


def test_artwork_and_poem_use_independent_seeds():
    # Same pool for both; a shared seed would tend to pick the same index.
    pool = [str(i) for i in range(50)]
    sel = DailyPicker().pick("2026-06-19", pool, pool)
    assert sel.artwork_id != sel.poem_id


def test_seen_items_are_excluded():
    picker = DailyPicker()
    seen = {"a1", "a2", "a3", "a4"}  # only a5 remains
    assert picker.pick("2026-06-19", ART, POEMS, seen=seen).artwork_id == "a5"


def test_all_seen_falls_back_to_full_pool_rather_than_failing():
    picker = DailyPicker()
    sel = picker.pick("2026-06-19", ART, POEMS, seen=set(ART) | set(POEMS))
    assert sel.artwork_id in ART
    assert sel.poem_id in POEMS


def test_empty_pool_raises():
    with pytest.raises(ValueError):
        DailyPicker().pick("2026-06-19", [], POEMS)
