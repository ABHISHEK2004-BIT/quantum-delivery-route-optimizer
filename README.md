# RouteLab — Quantum Delivery Route Optimizer

A polished Streamlit prototype for delivery route planning with real road-network distance estimates and an optional quantum-inspired research comparison.

## What is included

- Depot and delivery-stop address lookup using OpenStreetMap/Nominatim
- Browser geolocation for the depot (requires permission and localhost or HTTPS)
- Road-distance matrix and route geometry from the public OSRM demo server
- Interactive map with depot, stops, and optimized driving path
- Fast exact classical TSP solver using Held–Karp dynamic programming
- Optional QAOA comparison using Qiskit on a local simulator
- Caching for repeated geocoding, road matrices, and route geometry
- Professional Streamlit dashboard and demo locations around Mumbai

## Speed expectations

The **classical route optimization** is designed to complete in seconds for normal demo runs (up to 15 total locations). Address lookup and public road-service requests depend on internet/service response time and are not guaranteed to finish within 10 seconds. The optional QAOA simulator can take longer; it is separate from the fast recommended route so it does not block route generation.

## Requirements

Use Python 3.11 on Windows for the most predictable dependency compatibility.

### Windows PowerShell

```powershell
cd path\to\quantum_delivery_route_optimizer
py -3.11 -m venv .venv311
.\.venv311\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m streamlit run app.py
```

If PowerShell blocks activation, use Command Prompt:

```bat
cd /d path\to\quantum_delivery_route_optimizer
py -3.11 -m venv .venv311
.venv311\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL Streamlit prints, usually `http://localhost:8501`.

## Quick demo

1. Click **Load Mumbai demo locations** in the sidebar.
2. Click **Confirm locations & calculate road distances**.
3. Click **Generate optimized route**.
4. Optionally click **Run QAOA comparison** for up to four total locations.

## Notes and limitations

- Public Nominatim and OSRM endpoints are rate-limited demo services, not a production SLA. Use a suitable provider or self-hosted service for commercial deployment.
- Public endpoints need internet access. The Mumbai demo locations are prefilled, but road-distance calculation still needs OSRM.
- Current implementation is single-vehicle TSP, not vehicle routing with time windows/capacity.
- Distances do not account for live traffic, delivery windows, vehicle restrictions, or stops/parking.
- QAOA is a heuristic experiment. The model uses n² assignment variables, is intentionally limited to 3–4 total locations, and may produce a worse route or fail to return a feasible solution. No quantum advantage is claimed.
- Do not bypass Windows security/Code Integrity controls to install or load blocked binary packages.

## Project structure

```text
app.py                 Streamlit UI and workflow
classical_solver.py    Fast exact Held–Karp TSP solver
quantum_solver.py      QAOA TSP experiment
location_services.py   Geocoding and OSRM road-routing adapter
route_utils.py         Route and synthetic-data utilities
requirements.txt       Python dependencies
```
