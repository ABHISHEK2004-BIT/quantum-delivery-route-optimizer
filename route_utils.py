"""Small route utility helpers."""
import numpy as np

def route_distance(distance_matrix, route):
    d = np.asarray(distance_matrix, dtype=float)
    return float(sum(d[route[i], route[i+1]] for i in range(len(route)-1)))

def make_distance_matrix(number_of_locations, seed=7):
    """Create deterministic synthetic points for optional offline experiments."""
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0, 100, size=(number_of_locations, 2))
    diff = coords[:, None, :] - coords[None, :, :]
    distances = np.sqrt((diff**2).sum(axis=2))
    return coords, distances
