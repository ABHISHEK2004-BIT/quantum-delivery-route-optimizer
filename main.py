"""FastAPI backend for the Quantum Delivery Route Optimizer hackathon app."""
from pathlib import Path
from typing import Any
import logging
import os
import time
import traceback

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from classical_solver import solve_classical
from quantum_solver import solve_qaoa
from location_services import (
    search_address,
    reverse_address,
    get_road_distance_matrix,
    get_road_route_geometry,
)

BASE_DIR = Path(__file__).resolve().parent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("routelab")

app = FastAPI(title="RouteLab API", version="1.1.0")
app.mount("/static", StaticFiles(directory=str(BASE_DIR)), name="static")


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=250)
    limit: int = Field(default=5, ge=1, le=5)


class ReverseRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class Location(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    address: str = Field(min_length=1, max_length=500)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class OptimizeRequest(BaseModel):
    locations: list[Location] = Field(min_length=3, max_length=15)


class QAOARequest(BaseModel):
    locations: list[Location] = Field(min_length=3, max_length=4)
    reps: int = Field(default=1, ge=1, le=2)
    maxiter: int = Field(default=3, ge=1, le=10)


@app.get("/")
def index():
    index_path = BASE_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=500, detail="Frontend file index.html was not found.")
    return FileResponse(index_path)


@app.get("/health")
def health():
    return {"status": "ok", "service": "RouteLab API", "version": app.version}


@app.post("/api/search")
def api_search(request: SearchRequest):
    try:
        return {"results": search_address(request.query, limit=request.limit)}
    except Exception as exc:
        logger.exception("Address search failed")
        raise HTTPException(
            status_code=502,
            detail=f"Address search failed ({type(exc).__name__}): {exc}",
        ) from exc


@app.post("/api/reverse")
def api_reverse(request: ReverseRequest):
    try:
        return {"address": reverse_address(request.lat, request.lon)}
    except Exception as exc:
        logger.exception("Reverse geocoding failed")
        raise HTTPException(
            status_code=502,
            detail=f"Reverse geocoding failed ({type(exc).__name__}): {exc}",
        ) from exc


def _prepare_locations(items: list[Location]) -> list[dict[str, Any]]:
    result = [item.model_dump() for item in items]

    rounded_coordinates = [
        (round(item["lat"], 6), round(item["lon"], 6))
        for item in result
    ]
    if len(set(rounded_coordinates)) != len(rounded_coordinates):
        raise HTTPException(
            status_code=400,
            detail="Two or more locations have identical coordinates. Choose different locations.",
        )

    return result


def _normalize_route(route, n: int) -> list[int]:
    route = [int(i) for i in route]

    if not route or any(i < 0 or i >= n for i in route):
        raise ValueError("Solver returned location indexes outside the valid range.")

    if route[0] != 0:
        route.insert(0, 0)
    if route[-1] != 0:
        route.append(0)

    # The first and last entries are depot index 0. Every other location
    # must occur exactly once in between.
    if sorted(route[1:-1]) != list(range(1, n)):
        raise ValueError(
            "Solver did not return a valid tour visiting every stop exactly once."
        )

    return route


def _get_matrix(locations: list[dict[str, Any]]):
    """Get a road-distance matrix and report upstream failures clearly."""
    try:
        return get_road_distance_matrix(locations)
    except Exception as exc:
        logger.exception("Could not build road-distance matrix")
        raise HTTPException(
            status_code=502,
            detail=(
                "Could not calculate road distances. Check internet access and try again. "
                f"Details: {type(exc).__name__}: {exc}"
            ),
        ) from exc


def _get_geometry(locations, route):
    """Use OSRM geometry when available; fall back to straight map segments."""
    try:
        return get_road_route_geometry(locations, route)
    except Exception:
        logger.exception("Road route geometry unavailable; using straight-line map segments")
        return [[locations[i]["lat"], locations[i]["lon"]] for i in route]


@app.post("/api/optimize")
def api_optimize(request: OptimizeRequest):
    locations = _prepare_locations(request.locations)

    matrix_started = time.perf_counter()
    matrix = _get_matrix(locations)
    matrix_seconds = time.perf_counter() - matrix_started

    try:
        solver_started = time.perf_counter()
        route, cost = solve_classical(matrix)
        solver_seconds = time.perf_counter() - solver_started
        route = _normalize_route(route, len(locations))
        geometry = _get_geometry(locations, route)

        return {
            "route": route,
            "distance_km": round(float(cost), 3),
            "locations": locations,
            "geometry": geometry,
            "timing": {
                "road_matrix_seconds": round(matrix_seconds, 3),
                "classical_seconds": round(solver_seconds, 4),
                "total_seconds": round(matrix_seconds + solver_seconds, 3),
            },
            "matrix_km": matrix.tolist(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Classical route optimization failed")
        raise HTTPException(
            status_code=500,
            detail=f"Route optimization failed ({type(exc).__name__}): {exc}",
        ) from exc


@app.post("/api/qaoa")
def api_qaoa(request: QAOARequest):
    locations = _prepare_locations(request.locations)

    # Keep road-service failures distinct from QAOA failures. This helps identify
    # whether the error is network-related or comes from the quantum solver.
    matrix = _get_matrix(locations)

    started = time.perf_counter()
    try:
        route, cost, details = solve_qaoa(
            matrix,
            reps=request.reps,
            maxiter=request.maxiter,
        )
        elapsed = time.perf_counter() - started

        route = _normalize_route(route, len(locations))
        geometry = _get_geometry(locations, route)

        details = dict(details or {})
        details.setdefault("runtime_seconds", round(elapsed, 3))

        return {
            "route": route,
            "distance_km": round(float(cost), 3),
            "locations": locations,
            "geometry": geometry,
            "runtime_seconds": round(elapsed, 3),
            "details": details,
        }

    except HTTPException:
        raise
    except Exception as exc:
        elapsed = time.perf_counter() - started
        logger.error(
            "QAOA failed after %.3f seconds: %s: %s",
            elapsed,
            type(exc).__name__,
            exc,
        )
        logger.error("QAOA traceback:\n%s", traceback.format_exc())

        # Return the exception type and message to the frontend while keeping
        # the full traceback in the server terminal for debugging.
        raise HTTPException(
            status_code=500,
            detail=(
                f"QAOA could not complete ({type(exc).__name__}): {exc}. "
                "The classical route remains available; see the server terminal for details."
            ),
        ) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        reload=False,
    )
