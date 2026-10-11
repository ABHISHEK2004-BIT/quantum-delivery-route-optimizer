import time
import html
import streamlit as st
import folium
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation

from classical_solver import solve_classical
from quantum_solver import solve_qaoa
from location_services import (
    search_address, reverse_address,
    get_road_distance_matrix, get_road_route_geometry,
)

st.set_page_config(
    page_title="RouteLab | Quantum Delivery Optimizer",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
:root { --ink:#172033; --muted:#667085; --brand:#5b5ce2; --brand2:#7c3aed; --line:#e8eaf2; }
html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
.stApp { background:linear-gradient(180deg,#f7f8fc 0%,#ffffff 34%); color:var(--ink); }
.block-container { padding-top:1.6rem; max-width:1440px; }
h1,h2,h3 { font-family:'Space Grotesk',sans-serif !important; letter-spacing:-.035em; color:#172033; }
.hero { padding:1.5rem 1.65rem; border-radius:22px; background:linear-gradient(120deg,#171b35 0%,#34377b 58%,#5b5ce2 100%); color:white; margin-bottom:1.25rem; box-shadow:0 14px 34px rgba(43,45,110,.16); }
.hero-kicker { text-transform:uppercase; font-size:.72rem; letter-spacing:.16em; font-weight:700; color:#c7c8ff; margin-bottom:.6rem; }
.hero-title { font-family:'Space Grotesk',sans-serif; font-size:2.25rem; font-weight:700; line-height:1.1; letter-spacing:-.05em; color:#fff; }
.hero-sub { color:#e3e5ff; margin-top:.65rem; max-width:760px; font-size:1rem; }
.pill { display:inline-block; border:1px solid rgba(255,255,255,.28); color:#f1f2ff; padding:.32rem .65rem; border-radius:999px; font-size:.75rem; margin:1rem .35rem 0 0; }
.section-card { background:white; border:1px solid var(--line); border-radius:18px; padding:1.15rem 1.2rem; box-shadow:0 4px 16px rgba(22,32,51,.035); margin-bottom:1rem; }
.eyebrow { font-size:.72rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase; color:#6869d9; margin-bottom:.3rem; }
.small-muted { color:#667085; font-size:.9rem; }
.step { display:flex; align-items:center; gap:.7rem; font-weight:700; margin-bottom:.6rem; }
.step-num { display:inline-flex; width:28px; height:28px; align-items:center; justify-content:center; border-radius:9px; color:#fff; background:#5b5ce2; font-size:.85rem; }
div[data-testid="stMetric"] { background:#fff; border:1px solid #e8eaf2; padding:1rem 1.05rem; border-radius:16px; box-shadow:0 4px 14px rgba(22,32,51,.03); }
div[data-testid="stMetricLabel"] { color:#667085; }
.stButton>button[kind="primary"] { border:0; border-radius:12px; background:linear-gradient(100deg,#5455dc,#7c3aed); font-weight:700; min-height:2.8rem; box-shadow:0 5px 14px rgba(91,92,226,.2); }
.stButton>button { border-radius:11px; }
div[data-testid="stExpander"] { border:1px solid var(--line); border-radius:14px; background:#fff; }
footer {visibility:hidden;}
</style>
<div class="hero">
  <div class="hero-kicker">Hybrid optimization workspace</div>
  <div class="hero-title">RouteLab <span style="color:#bfc0ff">/</span> Delivery Optimizer</div>
  <div class="hero-sub">Plan a practical delivery loop from a depot, compare a fast classical optimizer with an experimental QAOA solver, and inspect the route on a road map.</div>
  <span class="pill">OpenStreetMap road distances</span><span class="pill">Classical route in seconds</span><span class="pill">QAOA experiment</span>
</div>
""", unsafe_allow_html=True)

# ---- helpers ----
def init_state():
    defaults = {
        "depot_selected": None, "depot_results": [], "depot_query": "",
        "depot_request_location": False, "stops_count": 3,
        "locations": None, "distance_matrix": None, "route_results": None,
        "route_signature": None, "map_pin": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    for i in range(1, 8):
        for suffix, default in [("selected", None), ("results", []), ("query", "")]:
            key = f"stop_{i}_{suffix}"
            if key not in st.session_state:
                st.session_state[key] = default

def location_picker(label, key, allow_current=False):
    selected_key, query_key, results_key = f"{key}_selected", f"{key}_query", f"{key}_results"
    c1, c2 = st.columns([4, 1])
    with c1:
        st.text_input(label, key=query_key, placeholder="Building, street, area, city")
    with c2:
        st.write("")
        search_clicked = st.button("Search", key=f"{key}_search", use_container_width=True)
    if search_clicked:
        q = st.session_state[query_key].strip()
        if not q:
            st.warning("Enter an address or place name first.")
        else:
            try:
                with st.spinner("Looking up address…"):
                    st.session_state[results_key] = search_address(q, limit=5)
                if not st.session_state[results_key]:
                    st.warning("No match found. Try including the city and state.")
            except Exception as e:
                st.error(f"Address lookup failed: {e}")
    results = st.session_state[results_key]
    if results:
        selected_index = st.selectbox(
            "Search results", range(len(results)),
            format_func=lambda i: results[i]["address"],
            key=f"{key}_choice",
        )
        if st.button("Use selected address", key=f"{key}_use", type="secondary"):
            st.session_state[selected_key] = dict(results[selected_index])
            st.session_state.route_results = None
            st.rerun()
    if allow_current:
        if st.button("📍 Use my current location", key=f"{key}_current"):
            st.session_state.depot_request_location = True
            st.rerun()
        if st.session_state.depot_request_location:
            st.caption("Allow browser location access when prompted. Geolocation requires localhost or HTTPS.")
            try:
                data = streamlit_geolocation()
                if isinstance(data, dict):
                    coords = data.get("coords", data)
                    lat, lon = coords.get("latitude"), coords.get("longitude")
                    if lat is not None and lon is not None:
                        lat, lon = float(lat), float(lon)
                        address = reverse_address(lat, lon)
                        st.session_state[selected_key] = {"address": address, "lat": lat, "lon": lon}
                        st.session_state.depot_request_location = False
                        st.session_state.route_results = None
                        st.rerun()
            except Exception as e:
                st.error(f"Could not read browser location: {e}")
    selected = st.session_state[selected_key]
    if selected:
        st.success(f"Selected: {selected['address']}")
    return selected

def route_label(route, locations):
    return "  →  ".join("DEPOT" if i == 0 else locations[i]["name"] for i in route)

def build_map(locations, route=None, key="map"):
    center = [sum(p["lat"] for p in locations)/len(locations), sum(p["lon"] for p in locations)/len(locations)]
    m = folium.Map(location=center, zoom_start=12, tiles="OpenStreetMap", control_scale=True)
    if route:
        try:
            geometry = get_road_route_geometry(locations, route)
            folium.PolyLine(geometry, color="#5b5ce2", weight=6, opacity=.9, tooltip="Optimized driving route").add_to(m)
        except Exception:
            geometry = [[locations[i]["lat"], locations[i]["lon"]] for i in route]
            folium.PolyLine(geometry, color="#f97316", weight=4, dash_array="7, 9", tooltip="Stop order (road geometry unavailable)").add_to(m)
    for i, p in enumerate(locations):
        label = "DEPOT" if i == 0 else p["name"].upper()
        color = "green" if i == 0 else "blue"
        folium.Marker([p["lat"], p["lon"]], tooltip=label,
            popup=folium.Popup(f"<b>{html.escape(label)}</b><br>{html.escape(p['address'])}", max_width=320),
            icon=folium.Icon(color=color, icon="flag" if i == 0 else "shopping-bag", prefix="fa")).add_to(m)
    return m

def get_route_signature(locations):
    return tuple((round(p["lat"], 5), round(p["lon"], 5)) for p in locations)

init_state()

with st.sidebar:
    st.markdown("### ⚙️ Workspace")
    st.markdown("<div class='small-muted'>Tune the size of your delivery run.</div>", unsafe_allow_html=True)
    stop_count = st.slider("Delivery stops", 2, 7, int(st.session_state.stops_count), help="Classical optimization supports up to 15 locations. QAOA is kept to a very small instance.")
    st.session_state.stops_count = stop_count
    st.divider()
    st.markdown("**Optimization mode**")
    st.caption("Fast route planning is the default. QAOA is an optional experiment and can take longer on a local simulator.")
    st.markdown("**Demo data**")
    if st.button("Load Mumbai demo locations", use_container_width=True):
        demo = [
            {"name":"Depot","address":"Chhatrapati Shivaji Maharaj Terminus, Mumbai, Maharashtra, India","lat":18.9398,"lon":72.8355},
            {"name":"Stop 1","address":"Gateway of India, Mumbai, Maharashtra, India","lat":18.9220,"lon":72.8347},
            {"name":"Stop 2","address":"Marine Drive, Mumbai, Maharashtra, India","lat":18.9430,"lon":72.8238},
            {"name":"Stop 3","address":"Dadar Station, Mumbai, Maharashtra, India","lat":19.0180,"lon":72.8420},
        ]
        st.session_state.depot_selected = demo[0]
        for i in range(1, 8):
            st.session_state[f"stop_{i}_selected"] = demo[i] if i < len(demo) else None
        st.session_state.stops_count = 3
        st.session_state.locations = None
        st.session_state.distance_matrix = None
        st.session_state.route_results = None
        st.rerun()
    st.divider()
    st.caption("Demo build • OSRM + OpenStreetMap • Python / Streamlit / Qiskit")

# ---- setup ----
st.markdown("## 1 · Build your delivery run")
st.markdown("<div class='small-muted'>Choose a depot and each drop-off. Search addresses or use your browser's current location for the depot.</div>", unsafe_allow_html=True)
with st.container(border=True):
    st.markdown("<div class='step'><span class='step-num'>1</span> Depot / starting point</div>", unsafe_allow_html=True)
    depot = location_picker("Depot address", "depot", allow_current=True)

with st.container(border=True):
    st.markdown("<div class='step'><span class='step-num'>2</span> Delivery stops</div>", unsafe_allow_html=True)
    stop_cols = st.columns(2)
    stops = []
    for i in range(1, stop_count + 1):
        with stop_cols[(i-1) % 2]:
            with st.expander(f"Drop-off {i}", expanded=(i <= 2)):
                stop = location_picker(f"Address for stop {i}", f"stop_{i}")
                stops.append(stop)

# Optional single-map pin picker (keeps the interface lighter than rendering one map per field).
st.markdown("#### Or select a point directly on the map")
st.caption("Click the map, choose which field to update, then confirm the pin.")
map_center = [depot["lat"], depot["lon"]] if depot else [19.0760, 72.8777]
pin_map = folium.Map(location=map_center, zoom_start=11 if not depot else 13, tiles="OpenStreetMap", control_scale=True)
for idx, loc in enumerate(([depot] if depot else []) + [s for s in stops if s]):
    folium.CircleMarker([loc["lat"], loc["lon"]], radius=6, color="#5b5ce2", fill=True, fill_opacity=.85,
                        tooltip=loc.get("name", "Selected location")).add_to(pin_map)
pin_result = st_folium(pin_map, width=None, height=310, key="pin_picker_map")
if pin_result and pin_result.get("last_clicked"):
    click = pin_result["last_clicked"]
    signature = (round(float(click["lat"]), 6), round(float(click["lng"]), 6))
    if signature != st.session_state.get("map_pin_signature"):
        st.session_state.map_pin_signature = signature
        st.session_state.map_pin = {"lat": signature[0], "lon": signature[1]}
if st.session_state.map_pin:
    pin = st.session_state.map_pin
    st.info(f"Map pin: {pin['lat']:.6f}, {pin['lon']:.6f}")
    target_options = ["Depot"] + [f"Stop {i}" for i in range(1, stop_count + 1)]
    target = st.selectbox("Apply map pin to", target_options, key="map_pin_target")
    if st.button("Use map pin for selected field", key="apply_map_pin"):
        try:
            with st.spinner("Resolving the map pin address…"):
                address = reverse_address(pin["lat"], pin["lon"])
            value = {"address": address, "lat": pin["lat"], "lon": pin["lon"]}
            if target == "Depot":
                st.session_state.depot_selected = value
            else:
                target_index = int(target.split()[-1])
                value["name"] = target
                st.session_state[f"stop_{target_index}_selected"] = value
            st.session_state.locations = None
            st.session_state.distance_matrix = None
            st.session_state.route_results = None
            st.session_state.map_pin = None
            st.rerun()
        except Exception as e:
            st.error(f"Could not resolve map pin: {e}")

ready = depot is not None and all(s is not None for s in stops)
if st.button("✓  Confirm locations & calculate road distances", type="primary", use_container_width=True, disabled=not ready):
    locations = [{**depot, "name":"Depot"}] + [{**s, "name":f"Stop {i}"} for i, s in enumerate(stops, start=1)]
    coords_sig = get_route_signature(locations)
    try:
        with st.spinner("Building a road-distance matrix…"):
            distances = get_road_distance_matrix(locations)
        st.session_state.locations = locations
        st.session_state.distance_matrix = distances
        st.session_state.route_results = None
        st.session_state.route_signature = coords_sig
        st.success(f"Ready to optimize: {len(locations)} locations connected by road-distance estimates.")
    except Exception as e:
        st.error(f"Could not calculate road distances: {e}")

locations = st.session_state.locations
distances = st.session_state.distance_matrix

if locations is not None and distances is not None:
    st.markdown("## 2 · Route overview")
    metrics = st.columns(3)
    metrics[0].metric("Locations", len(locations))
    metrics[1].metric("Delivery stops", len(locations)-1)
    metrics[2].metric("Distance source", "Road network")
    loc_rows = [{"Point": "Depot" if i == 0 else p["name"], "Address": p["address"], "Latitude": round(p["lat"], 5), "Longitude": round(p["lon"], 5)} for i,p in enumerate(locations)]
    with st.expander("Review addresses and coordinates"):
        st.dataframe(loc_rows, use_container_width=True, hide_index=True)
    st_folium(build_map(locations, key="overview"), width=None, height=390, key="overview_map")

    st.markdown("## 3 · Optimize")
    st.markdown("<div class='small-muted'>The recommended route is generated with a fast classical solver first. Optional QAOA provides a research comparison for up to four locations total.</div>", unsafe_allow_html=True)
    col_a, col_b = st.columns([3, 2])
    with col_a:
        if st.button("🚀 Generate optimized route", type="primary", use_container_width=True):
            start = time.perf_counter()
            try:
                route, cost = solve_classical(distances)
                elapsed = time.perf_counter() - start
                st.session_state.route_results = {
                    "classical": {"route": route, "cost": cost, "seconds": elapsed},
                    "qaoa": None,
                }
                st.rerun()
            except Exception as e:
                st.error(f"Route optimization failed: {e}")
    with col_b:
        qaoa_disabled = len(locations) > 4
        if st.button("⚛️ Run QAOA comparison", use_container_width=True, disabled=qaoa_disabled):
            results = st.session_state.route_results or {}
            start = time.perf_counter()
            try:
                qroute, qcost, details = solve_qaoa(distances, reps=1, maxiter=5)
                results["qaoa"] = {"route": qroute, "cost": qcost, "seconds": time.perf_counter()-start, "details": details}
                st.session_state.route_results = results
                st.rerun()
            except Exception as e:
                results["qaoa"] = {"error": str(e), "seconds": time.perf_counter()-start}
                st.session_state.route_results = results
                st.rerun()
    if qaoa_disabled:
        st.caption("QAOA is disabled above 4 locations because the assignment-variable encoding grows as n² qubits.")

    results = st.session_state.route_results
    if results and results.get("classical"):
        classical = results["classical"]
        st.markdown("## 4 · Recommended route")
        k1, k2, k3 = st.columns(3)
        k1.metric("Estimated road distance", f"{classical['cost']:.2f} km")
        k2.metric("Optimization time", f"{classical['seconds']:.3f} s")
        k3.metric("Stops to visit", len(locations)-1)
        st.markdown("<div class='section-card'><div class='eyebrow'>Recommended stop order</div><div style='font-size:1.03rem;font-weight:700;line-height:1.8'>" + html.escape(route_label(classical["route"], locations)) + "</div></div>", unsafe_allow_html=True)
        st_folium(build_map(locations, classical["route"], key="classical"), width=None, height=480, key="classical_route_map")
        st.caption("Distance is estimated from the road-network routing service. Live traffic, vehicle restrictions, and delivery time windows are not included.")

        qaoa = results.get("qaoa")
        if qaoa:
            st.markdown("## 5 · Quantum-classical comparison")
            if qaoa.get("error"):
                st.warning(f"QAOA could not complete: {qaoa['error']}")
            else:
                q1, q2, q3 = st.columns(3)
                q1.metric("QAOA candidate", f"{qaoa['cost']:.2f} km")
                q2.metric("QAOA runtime", f"{qaoa['seconds']:.2f} s")
                delta = (qaoa["cost"]-classical["cost"]) / max(classical["cost"], 1e-9) * 100
                q3.metric("Difference vs classical", f"{delta:+.2f}%")
                st_folium(build_map(locations, qaoa["route"], key="qaoa"), width=None, height=400, key="qaoa_route_map")
                with st.expander("QAOA experiment details"):
                    st.json(qaoa.get("details", {}))
                st.caption("QAOA is a heuristic experiment and is not guaranteed to beat the classical route. This is not evidence of quantum advantage.")
else:
    st.markdown("""
    <div class="section-card">
      <div class="eyebrow">Ready when you are</div>
      <h3 style="margin-top:.15rem">Choose your stops to begin</h3>
      <div class="small-muted">For a quick walkthrough, choose <b>Load Mumbai demo locations</b> in the sidebar, then confirm the locations and generate the route.</div>
    </div>
    """, unsafe_allow_html=True)

with st.expander("About this prototype · accuracy, speed & limits"):
    st.markdown("""
    - **Fast path:** the classical optimizer finds the best closed tour for the supplied road-distance matrix. Route generation is designed to finish in seconds for normal demo-sized runs.
    - **Road data:** distances and route geometry come from the public OSRM demo service with OpenStreetMap data. Public endpoints are rate-limited and are not a production SLA.
    - **Quantum experiment:** QAOA uses a local simulator and an assignment-variable TSP encoding. It is limited to four total locations in this app and may take longer than the classical route.
    - **Not live dispatch:** traffic, vehicle capacity, opening hours, delivery windows, and multi-vehicle routing are not modeled.
    - **No quantum advantage claim:** the project is an educational/hackathon comparison.
    """)
