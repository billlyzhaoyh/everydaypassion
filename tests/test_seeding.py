from everydaypassion.seeding import seed_for, shuffled


def test_seed_is_stable_for_a_key():
    assert seed_for("2026-06-19:artwork") == seed_for("2026-06-19:artwork")


def test_different_keys_give_different_seeds():
    assert seed_for("2026-06-19:artwork") != seed_for("2026-06-19:poem")


def test_shuffle_is_deterministic():
    items = list(range(20))
    assert shuffled(123, items) == shuffled(123, items)


def test_shuffle_is_a_permutation():
    items = list(range(20))
    assert sorted(shuffled(999, items)) == items


def test_shuffle_does_not_mutate_input():
    items = [1, 2, 3, 4]
    shuffled(7, items)
    assert items == [1, 2, 3, 4]


def test_different_seeds_usually_reorder():
    items = list(range(20))
    assert shuffled(1, items) != shuffled(2, items)
