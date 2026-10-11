"""Dependency-light smoke test for the classical solver."""
import numpy as np
from classical_solver import solve_classical

def test_solver():
    d = np.array([
        [0, 1, 4, 3],
        [1, 0, 2, 5],
        [4, 2, 0, 1],
        [3, 5, 1, 0],
    ], dtype=float)
    route, cost = solve_classical(d)
    assert route[0] == route[-1] == 0
    assert sorted(route[1:-1]) == [1, 2, 3]
    assert abs(cost - 7.0) < 1e-9

if __name__ == "__main__":
    test_solver()
    print("Classical solver smoke test passed.")
