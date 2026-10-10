"""Fast exact Traveling Salesperson Problem solver using Held–Karp dynamic programming."""
from functools import lru_cache
import numpy as np

def solve_classical(distance_matrix):
    """
    Return (closed_route, distance) with depot fixed at index 0.
    Held–Karp is O(n^2 * 2^n), much faster than checking all permutations.
    The app is designed for up to 15 total locations.
    """
    d = np.asarray(distance_matrix, dtype=float)
    if d.ndim != 2 or d.shape[0] != d.shape[1]:
        raise ValueError("Distance matrix must be square.")
    n = d.shape[0]
    if n < 3:
        raise ValueError("At least one depot and two delivery stops are required.")
    if n > 15:
        raise ValueError("This exact solver supports at most 15 total locations.")
    if not np.isfinite(d).all():
        raise ValueError("Distance matrix contains missing or invalid distances.")

    # DP state: (visited subset of non-depot cities, last city) -> (cost, parent).
    m = n - 1
    dp = {}
    parent = {}
    for j in range(1, n):
        mask = 1 << (j - 1)
        dp[(mask, j)] = float(d[0, j])
        parent[(mask, j)] = 0

    for mask in range(1, 1 << m):
        for j in range(1, n):
            bit_j = 1 << (j - 1)
            if not (mask & bit_j) or mask == bit_j:
                continue
            previous_mask = mask ^ bit_j
            best_cost, best_prev = float("inf"), None
            for k in range(1, n):
                if previous_mask & (1 << (k - 1)):
                    candidate = dp[(previous_mask, k)] + float(d[k, j])
                    if candidate < best_cost:
                        best_cost, best_prev = candidate, k
            dp[(mask, j)] = best_cost
            parent[(mask, j)] = best_prev

    full = (1 << m) - 1
    end = min(range(1, n), key=lambda j: dp[(full, j)] + float(d[j, 0]))
    total = dp[(full, end)] + float(d[end, 0])

    route_rev = [end]
    mask, current = full, end
    while mask:
        previous = parent[(mask, current)]
        mask ^= 1 << (current - 1)
        if previous == 0:
            break
        route_rev.append(previous)
        current = previous
    route = [0] + list(reversed(route_rev)) + [0]
    return route, float(total)
