const state = {
  depot: null, stops: [], searchResults: {}, optimized: null, qaoa: null,
  markers: [], routeLayer: null, markerLayer: null
};
const $ = (id) => document.getElementById(id);
const map = L.map("map", { zoomControl: true }).setView([19.076, 72.8777], 11);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19, attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);
state.markerLayer = L.layerGroup().addTo(map);

function notify(message, type = "") {
  const el = $("notice");
  el.textContent = message;
  el.className = `notice ${type}`.trim();
  el.classList.remove("hidden");
}
function clearNotice() { $("notice").classList.add("hidden"); }
function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
async function api(path, payload) {
  const response = await fetch(path, {
    method: "POST", headers: {"Content-Type":"application/json"},
    body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
}
function allLocations() {
  return state.depot && state.stops.every(Boolean)
    ? [{...state.depot, name:"Depot"}, ...state.stops.map((s,i)=>({...s,name:`Stop ${i+1}`}))]
    : [];
}
function setSelected(type, index, item) {
  if (type === "depot") state.depot = item;
  else state.stops[index] = item;
  state.optimized = null; state.qaoa = null;
  renderSelected(); renderMap(); updateButtons();
}
function renderSelected() {
  $("depot-selected").textContent = state.depot ? `✓ ${state.depot.address}` : "No depot selected";
  const count = Number($("stop-count").value);
  $("stops").innerHTML = Array.from({length:count}, (_,i) => {
    const stop = state.stops[i];
    return `<div class="stop-card">
      <div class="stop-title">DROP-OFF ${i+1}</div>
      <div class="search-row"><input id="stop-input-${i}" placeholder="Street, business, area" value="${stop ? escapeHtml(stop.address) : ""}"><button data-stop-search="${i}">Search</button></div>
      <div id="stop-results-${i}" class="results"></div>
      <div class="location-chip">${stop ? `✓ ${escapeHtml(stop.address)}` : "No stop selected"}</div>
    </div>`;
  }).join("");
  $("stops").querySelectorAll("[data-stop-search]").forEach(btn => btn.addEventListener("click", () => searchFor("stop", Number(btn.dataset.stopSearch))));
}
function updateButtons() {
  const ready = allLocations().length >= 3;
  $("optimize").disabled = !ready;
  $("qaoa").disabled = !(state.optimized && allLocations().length <= 4);
}
function renderMap(routeData = null) {
  state.markerLayer.clearLayers();
  if (state.routeLayer) { map.removeLayer(state.routeLayer); state.routeLayer = null; }
  const locs = routeData?.locations || allLocations();
  if (!locs.length) return;
  locs.forEach((p,i) => {
    L.marker([p.lat,p.lon]).bindPopup(`<b>${i===0?"DEPOT":escapeHtml(p.name || `Stop ${i}`)}</b><br>${escapeHtml(p.address)}`)
      .addTo(state.markerLayer);
  });
  if (routeData?.geometry?.length) {
    state.routeLayer = L.polyline(routeData.geometry, {color:"#5b5ce2",weight:5,opacity:.9}).addTo(map);
  }
  const bounds = L.latLngBounds(locs.map(p=>[p.lat,p.lon]));
  if (routeData?.geometry?.length) routeData.geometry.forEach(p=>bounds.extend(p));
  map.fitBounds(bounds.pad(.18), {maxZoom:14});
}
async function searchFor(type, index = 0) {
  clearNotice();
  const inputId = type === "depot" ? "depot" : `stop-input-${index}`;
  const query = $(inputId)?.value.trim();
  if (!query) return notify("Enter an address or place name first.", "error");
  const btn = type === "depot" ? document.querySelector('[data-search="depot"]') : document.querySelector(`[data-stop-search="${index}"]`);
  if (btn) { btn.disabled = true; btn.textContent = "Searching…"; }
  try {
    const data = await api("/api/search", {query, limit:5});
    const target = type === "depot" ? $("depot-results") : $(`stop-results-${index}`);
    target.innerHTML = "";
    if (!data.results.length) return notify("No address matches. Try adding city and state.", "error");
    data.results.forEach(item => {
      const option = document.createElement("button");
      option.className = "result-option";
      option.textContent = item.address;
      option.addEventListener("click", () => {
        setSelected(type,index,item);
        if (type === "depot") $("depot-results").innerHTML = "";
        else $(`stop-results-${index}`).innerHTML = "";
        notify(`${type === "depot" ? "Depot" : `Stop ${index+1}`} selected.`, "success");
      });
      target.appendChild(option);
    });
  } catch (e) { notify(e.message, "error"); }
  finally { if (btn) {btn.disabled=false;btn.textContent="Search";} }
}
document.querySelectorAll("[data-search]").forEach(btn => btn.addEventListener("click", () => searchFor("depot")));
$("stop-count").addEventListener("change", () => {
  const count = Number($("stop-count").value);
  state.stops = Array.from({length:count}, (_,i)=>state.stops[i] || null);
  renderSelected(); renderMap(); updateButtons();
});
$("use-location").addEventListener("click", () => {
  if (!navigator.geolocation) return notify("Browser geolocation is unavailable.", "error");
  notify("Requesting your location. Allow access in your browser.");
  navigator.geolocation.getCurrentPosition(async pos => {
    const {latitude:lat,longitude:lon}=pos.coords;
    try {
      const data = await api("/api/reverse",{lat,lon});
      setSelected("depot",0,{lat,lon,address:data.address});
      notify("Current location selected as the depot.", "success");
    } catch(e) { notify(e.message,"error"); }
  }, err => notify(`Location unavailable: ${err.message}. Use address search instead.`, "error"),
  {enableHighAccuracy:true,timeout:10000,maximumAge:60000});
});
$("demo").addEventListener("click", () => {
  const demo = [
    {address:"Chhatrapati Shivaji Maharaj Terminus, Mumbai, Maharashtra, India",lat:18.9398,lon:72.8355},
    {address:"Gateway of India, Mumbai, Maharashtra, India",lat:18.9220,lon:72.8347},
    {address:"Marine Drive, Mumbai, Maharashtra, India",lat:18.9430,lon:72.8238},
    {address:"Dadar Station, Mumbai, Maharashtra, India",lat:19.0180,lon:72.8420},
  ];
  $("stop-count").value="3";
  state.depot=demo[0]; state.stops=demo.slice(1).map((p,i)=>({...p,name:`Stop ${i+1}`}));
  state.optimized=null; state.qaoa=null;
  renderSelected();renderMap();updateButtons();
  notify("Mumbai demo locations loaded. Generate the route when ready.","success");
});
$("optimize").addEventListener("click", async () => {
  clearNotice();
  const locations=allLocations();
  if(!locations.length) return notify("Select a depot and every delivery stop first.","error");
  $("optimize").disabled=true;$("optimize").textContent="Calculating road distances and route…";
  try {
    const data=await api("/api/optimize",{locations});
    state.optimized=data;state.qaoa=null;
    $("stat-locations").textContent=data.locations.length;
    $("stat-distance").textContent=`${data.distance_km.toFixed(2)} km`;
    $("stat-time").textContent=`${data.timing.classical_seconds.toFixed(3)} s`;
    $("map-subtitle").textContent=`${data.locations.length-1} stops · road distance · ${data.timing.total_seconds.toFixed(1)} s total request`;
    $("route-order").className="route-order";
    $("route-order").innerHTML=data.route.map((idx,pos)=> {
      const name=idx===0?"DEPOT":`Stop ${idx}`;
      return `${pos+1}. ${escapeHtml(name)}${pos<data.route.length-1?" &nbsp;→&nbsp; ":""}`;
    }).join("");
    renderMap(data);updateButtons();
    notify("Optimized route generated successfully.","success");
  } catch(e) { notify(e.message,"error"); }
  finally {$("optimize").disabled=false;$("optimize").textContent="⚡ Generate optimized route";updateButtons();}
});
$("qaoa").addEventListener("click", async () => {
  if(!state.optimized)return;
  $("qaoa").disabled=true;$("qaoa").textContent="Running QAOA…";
  $("qaoa-status").textContent="Small-instance quantum simulator running. Classical route remains available.";
  $("qaoa-result").classList.add("hidden");
  try {
    const data=await api("/api/qaoa",{locations:state.optimized.locations,reps:1,maxiter:3});
    state.qaoa=data;
    const delta=((data.distance_km-state.optimized.distance_km)/Math.max(state.optimized.distance_km,1e-9))*100;
    const deltaLabel = `${delta >= 0 ? "+" : ""}${delta.toFixed(2)}%`;
    const deltaClass = delta <= 0 ? "good" : "warn";
    const routeMarkup = data.route.map((idx, pos) => {
      const isDepot = idx === 0;
      const name = isDepot ? "DEPOT" : `Stop ${idx}`;
      const icon = isDepot ? "⌂" : String(idx);
      const stop = `<span class="qaoa-stop ${isDepot ? "depot" : ""}"><span class="qaoa-stop-index">${icon}</span>${name}</span>`;
      return stop + (pos < data.route.length - 1 ? '<span class="qaoa-route-arrow">→</span>' : "");
    }).join("");
    $("qaoa-result").innerHTML = `
      <div class="qaoa-hero">
        <div class="qaoa-overline"><span class="qaoa-orb">⚛</span> Quantum-classical experiment</div>
        <div class="qaoa-headline">
          <div><div class="qaoa-distance">${data.distance_km.toFixed(2)} <span style="font-size:16px;letter-spacing:0">km</span></div><div class="qaoa-distance-label">QAOA candidate distance</div></div>
          <span class="qaoa-badge">Simulation complete</span>
        </div>
      </div>
      <div class="qaoa-body">
        <div class="qaoa-metrics">
          <div class="qaoa-metric"><div class="qaoa-metric-label"><span class="qaoa-metric-icon">◷</span> Runtime</div><div class="qaoa-metric-value">${data.runtime_seconds.toFixed(2)}<span style="font-size:11px"> s</span></div><div class="qaoa-metric-sub">QAOA execution</div></div>
          <div class="qaoa-metric"><div class="qaoa-metric-label"><span class="qaoa-metric-icon">↕</span> vs. classical</div><div class="qaoa-metric-value"><span class="qaoa-delta ${deltaClass}">${deltaLabel}</span></div><div class="qaoa-metric-sub">Distance difference</div></div>
          <div class="qaoa-metric"><div class="qaoa-metric-label"><span class="qaoa-metric-icon">⌖</span> Stops</div><div class="qaoa-metric-value">${data.route.length - 2}</div><div class="qaoa-metric-sub">Delivery locations</div></div>
        </div>
        <div class="qaoa-route-wrap">
          <div class="qaoa-route-top"><div class="qaoa-route-title">Candidate stop sequence</div><span class="qaoa-route-pill">DEPOT → DEPOT</span></div>
          <div class="qaoa-route-track">${routeMarkup}</div>
        </div>
        <div class="qaoa-compare"><span>Classical baseline</span><strong>${state.optimized.distance_km.toFixed(2)} km</strong></div>
        <div class="qaoa-footnote"><span class="qaoa-footnote-icon">ⓘ</span><span>Simulator experiment only. QAOA is heuristic and does not guarantee a better route. No quantum advantage is implied.</span></div>
        <div class="qaoa-status-line"><span class="status-dot"></span>Result calculated successfully</div>
      </div>`;
    $("qaoa-result").classList.remove("hidden");$("qaoa-status").textContent="Comparison complete.";
  } catch(e) {
    $("qaoa-status").textContent="QAOA failed; classical route is still available.";
    $("qaoa-result").innerHTML=`<div class="qaoa-error"><b>QAOA could not complete</b><br>${escapeHtml(e.message)}<br><span style="color:#777">Your classical route remains available.</span></div>`;
    $("qaoa-result").classList.remove("hidden");
  } finally {$("qaoa").textContent="⚛ Run QAOA comparison";updateButtons();}
});
renderSelected();updateButtons();
