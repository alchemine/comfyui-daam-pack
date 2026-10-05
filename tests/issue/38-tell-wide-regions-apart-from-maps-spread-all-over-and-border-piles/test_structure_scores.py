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


# A standing figure in the middle, its feet at the bottom edge.
FIGURE = np.exp(-((((y - 38) / 30) ** 2 + ((x - 32) / 20) ** 2) ** 2))


def background():
    # Like bathroom: high everywhere around the figure, out to the edges.
    return 1 - FIGURE


def spread():
    # Like best quality: mid to high all over, with only the head low.
    centres = np.random.default_rng(0).integers(0, SIZE, (60, 2))
    texture = sum(blob(cy, cx, 3) for cy, cx in centres)
    return 0.4 + 0.5 * texture / texture.max() - 0.4 * blob(14, 32, 5)


def test_background_scores_yellow(daam):
    assert YELLOW <= score(daam, background()) < BLUE


def test_background_scores_above_spread(daam):
    assert score(daam, background()) > score(daam, spread())
