import numpy as np

SIZE = 64
y, x = np.mgrid[0:SIZE, 0:SIZE]
# Explorer colour cuts: blue from 0.75, yellow from 0.5.
BLUE = 0.75
YELLOW = 0.5


def blob(cy, cx, radius):
    return np.exp(-((y - cy) ** 2 + (x - cx) ** 2) / (2 * radius**2))


def score(daam, heat):
    return daam.structure_scores(heat[None].astype(np.float32))[0]


def test_narrow_region_scores_blue(daam):
    # Like an eye: a few cells on a flat, low rest.
    assert score(daam, blob(32, 32, 3)) >= BLUE


def test_wide_region_scores_yellow(daam):
    # Like a body: a large region on a flat, low rest.
    assert YELLOW <= score(daam, blob(24, 32, 14)) < BLUE


def test_map_spread_all_over_scores_grey(daam):
    # Like a style tag: blobs over the whole picture, mid to high everywhere.
    centres = np.random.default_rng(0).integers(0, SIZE, (200, 2))
    heat = sum(blob(cy, cx, 3) for cy, cx in centres)
    assert score(daam, heat) < YELLOW


def test_border_pile_scores_lowest(daam):
    noise = 0.05 * np.random.default_rng(0).random((SIZE, SIZE))
    to_edge = np.minimum.reduce([y, x, SIZE - 1 - y, SIZE - 1 - x])
    frame = np.maximum(0, 1 - to_edge / 4)
    assert score(daam, frame + noise) < 0.1
    assert score(daam, blob(0, 0, 3) + noise) < 0.1
