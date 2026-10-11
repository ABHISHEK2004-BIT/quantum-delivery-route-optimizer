# RouteLab — Quantum Delivery Route Optimizer (Hackathon upload)

This version uses the required top-level entry points:
- `main.py` — FastAPI backend
- `index.html` — browser UI
- `main.js` — interactive frontend
- `styles.css` — presentation layer
- `classical_solver.py` — Held–Karp exact TSP solver
- `quantum_solver.py` — small-instance QAOA experiment
- `location_services.py` — Nominatim geocoding and OSRM road-distance adapter

## Run locally

Use Python 3.11+ in a virtual environment:

```bash
py -3.11 -m venv .venv311
.venv311\Scripts\activate.bat
python -m pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`.

If your platform automatically launches the top-level `main.py`, it may run it as a script rather than an ASGI app. If so, add this to the bottom of `main.py`:

```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
```

## Demo flow

1. Load Mumbai demo locations, or search for a depot and each delivery stop.
2. Generate an optimized route.
3. Optionally run QAOA for at most four total locations.
4. Compare route distance and runtime.

## Notes

- The road matrix and route geometry use public OSRM/OpenStreetMap demo services. Internet access is required; public endpoints are rate-limited and do not guarantee a 10-second end-to-end response.
- The classical route optimizer uses Held–Karp dynamic programming, which is exact but exponential. It supports up to 15 total locations in this demo.
- QAOA runs on a local simulator and can take longer. The app keeps the classical result visible if QAOA fails. No quantum advantage is claimed.
- Browser geolocation requires user permission and a secure context (localhost or HTTPS).
