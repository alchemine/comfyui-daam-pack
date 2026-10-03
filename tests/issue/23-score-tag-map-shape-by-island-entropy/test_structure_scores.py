import numpy as np

SIZE = 64
y, x = np.mgrid[0:SIZE, 0:SIZE]


def blob(cy, cx, radius):
    return np.exp(-((y - cy) ** 2 + (x - cx) ** 2) / (2 * radius**2))


def score(daam, heat):
    return daam.structure_scores(heat[None].astype(np.float32))[0]


def test_one_island_scores_high_whatever_its_size(daam):
    assert score(daam, blob(32, 32, 2)) > 0.7
    assert score(daam, blob(32, 32, 10)) > 0.7


def test_two_islands_still_count(daam):
    assert score(daam, blob(26, 22, 2) + blob(26, 42, 2)) > 0.7


def test_sprinkled_map_scores_low(daam):
    centres = np.random.default_rng(0).integers(8, SIZE - 8, (12, 2))
    heat = sum(blob(cy, cx, 1.5) for cy, cx in centres)
    assert score(daam, heat) < 0.5


def test_red_background_scores_low(daam):
    heat = np.clip(np.hypot(y - 32, x - 32) / 32, 0, 1)
    assert score(daam, heat) < 0.1


def test_corner_pile_does_not_count(daam):
    heat = blob(0, 0, 3) + 0.05 * np.random.default_rng(0).random((SIZE, SIZE))
    assert score(daam, heat) < 0.5
