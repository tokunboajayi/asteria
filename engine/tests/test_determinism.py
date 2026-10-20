"""RocketPy's parachute trigger noise must not make rebuilds differ."""

import numpy as np

from asteria.rockets.notebook import RNG_SEED, seed_rng


def test_seed_rng_repeats_the_same_noise() -> None:
    seed_rng()
    first = np.random.normal(0, 8.3, 50)
    np.random.normal(0, 1, 7)  # unrelated draws in between must not matter after reseeding
    seed_rng()
    assert np.array_equal(first, np.random.normal(0, 8.3, 50))


def test_seed_is_fixed() -> None:
    assert RNG_SEED == 20240510
