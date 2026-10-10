"""Address lookup and road routing adapters for OpenStreetMap/Nominatim and OSRM.

The public demo services are rate-limited. Use a commercial/self-hosted provider
for production workloads. Network calls have finite timeouts and cacheable inputs.
"""
from functools import lru_cache
from typing import Iterable
import requests
import numpy as np
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

OSRM_BASE_URL = "https://router.project-osrm.org"
USER_AGENT = "RouteLab-Quantum-Delivery-Optimizer/1.0 (educational demo)"
_geocoder = Nominatim(user_agent=USER_AGENT, timeout=7)
_geocode = RateLimiter(_geocoder.geocode, min_delay_seconds=1.1, swallow_exceptions=True)
_reverse = RateLimiter(_geocoder.reverse, min_delay_seconds=1.1, swallow_exceptions=True)
_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT})

def _loc_dict(result):
    if result is None:
        return None
    return {"address": str(result.address), "lat": float(result.latitude), "lon": float(result.longitude)}

@lru_cache(maxsize=128)
def _search_cached(query, limit):
    found = _geocode(query, exactly_one=False, limit=limit, addressdetails=True)
    return tuple((_loc_dict(item)["address"], _loc_dict(item)["lat"], _loc_dict(item)["lon"]) for item in (found or []))

def search_address(query: str, limit: int = 5):
    query = str(query or "").strip()
    if not query:
        raise ValueError("Enter an address or place name.")
    try:
        return [{"address": a, "lat": lat, "lon": lon} for a, lat, lon in _search_cached(query, max(1, min(int(limit), 5)))]
    except Exception as exc:
        raise RuntimeError(f"Address search is temporarily unavailable: {exc}") from exc

@lru_cache(maxsize=256)
def _reverse_cached(lat, lon):
    result = _reverse((lat, lon), exactly_one=True, language="en")
    return str(result.address) if result else f"{lat:.6f}, {lon:.6f}"

def reverse_address(lat, lon):
    try:
        return _reverse_cached(round(float(lat), 6), round(float(lon), 6))
    except Exception:
        return f"{float(lat):.6f}, {float(lon):.6f}"

def _validate_locations(locations: Iterable[dict]):
    locations = list(locations)
    if len(locations) < 2:
        raise ValueError("At least two locations are required.")
    normalized = []
    for i, item in enumerate(locations):
        try:
            lat, lon = float(item["lat"]), float(item["lon"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Location {i+1} is missing valid coordinates.") from exc
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError(f"Location {i+1} has coordinates outside valid ranges.")
        normalized.append((lat, lon))
    return normalized

@lru_cache(maxsize=64)
def _road_matrix_cached(coords):
    coordinate_string = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in coords)
    url = f"{OSRM_BASE_URL}/table/v1/driving/{coordinate_string}"
    response = _session.get(url, params={"annotations":"distance"}, timeout=(3.05, 7))
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != "Ok" or payload.get("distances") is None:
        raise RuntimeError(payload.get("message", "Routing service did not return a distance matrix."))
    matrix = np.asarray(payload["distances"], dtype=float) / 1000.0
    if matrix.shape != (len(coords), len(coords)) or not np.isfinite(matrix).all():
        raise RuntimeError("Routing service returned incomplete road distances.")
    return tuple(tuple(float(x) for x in row) for row in matrix)

def get_road_distance_matrix(locations):
    coords = tuple(_validate_locations(locations))
    try:
        return np.asarray(_road_matrix_cached(coords), dtype=float)
    except requests.Timeout as exc:
        raise RuntimeError("The road-distance service timed out. Try again in a moment.") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not reach the road-distance service: {exc}") from exc

@lru_cache(maxsize=128)
def _route_geometry_cached(coords, route):
    ordered = [coords[i] for i in route]
    coordinate_string = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in ordered)
    url = f"{OSRM_BASE_URL}/route/v1/driving/{coordinate_string}"
    response = _session.get(url, params={"overview":"full", "geometries":"geojson", "steps":"false"}, timeout=(3.05, 7))
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != "Ok" or not payload.get("routes"):
        raise RuntimeError(payload.get("message", "No road geometry available."))
    return tuple((float(lat), float(lon)) for lon, lat in payload["routes"][0]["geometry"]["coordinates"])

def get_road_route_geometry(locations, route):
    coords = tuple(_validate_locations(locations))
    return list(_route_geometry_cached(coords, tuple(int(i) for i in route)))
