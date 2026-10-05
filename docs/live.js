// Live data panel: reads the Oil Data read API and renders hourly/daily marts.
// Pure helpers are exported for the Node tests; the DOM part only runs in a browser.
(() => {
  const DEFAULT_API = "http://localhost:8000";
  const POLL_MS = 15000;
  const TIMEOUT_MS = 8000;
  const MAX_ROWS = 1000;
  const STORAGE_KEY = "oil-data-api";
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  const METRICS = {
    avg_pressure_bar: { label: "Avg pressure", unit: "bar" },
    avg_temperature_c: { label: "Avg temperature", unit: "°C" },
    avg_flow_m3_h: { label: "Avg flow rate", unit: "m³/h" },
    max_water_cut_pct: { label: "Max water cut", unit: "%" },
  };

  const pad2 = (n) => String(n).padStart(2, "0");

  // Returns a clean base URL, or null when the input is not an http(s) address.
  function normalizeBase(raw) {
    if (typeof raw !== "string") return null;
    let url;
    try { url = new URL(raw.trim()); } catch { return null; }
    if (url.protocol !== "http:" && url.protocol !== "https:") return null;
    if (url.username || url.password) return null;
    return (url.origin + url.pathname).replace(/\/+$/, "");
  }

  function formatPeriod(iso, granularity) {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso);
    const day = `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}`;
    return granularity === "daily" ? day : `${day}, ${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())}`;
  }

  function formatTimestamp(iso) {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso);
    return `${d.getUTCFullYear()}-${pad2(d.getUTCMonth() + 1)}-${pad2(d.getUTCDate())} ` +
      `${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())}:${pad2(d.getUTCSeconds())} UTC`;
  }

  // Maps mart rows to SVG coordinates on the same 700x260 canvas as the lab chart.
  function chartGeometry(items, metric, width = 700, top = 36, bottom = 222, inset = 12) {
    if (!items.length) return null;
    const rows = items.map((item) => ({ item, t: Date.parse(item.period_start), v: item[metric] }));
    const values = rows.map((r) => r.v);
    let lo = Math.min(...values);
    let hi = Math.max(...values);
    if (lo === hi) { const spread = Math.abs(lo) * 0.05 || 1; lo -= spread; hi += spread; }
    const t0 = rows[0].t;
    const t1 = rows[rows.length - 1].t;
    const points = rows.map((r) => ({
      x: t1 === t0 ? width / 2 : inset + ((r.t - t0) / (t1 - t0)) * (width - 2 * inset),
      y: bottom - ((r.v - lo) / (hi - lo)) * (bottom - top),
      item: r.item,
      value: r.v,
    }));
    const line = points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
    const area = `M${points[0].x.toFixed(1)} ${bottom} ` +
      points.map((p) => `L${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ") +
      ` L${points[points.length - 1].x.toFixed(1)} ${bottom} Z`;
    return { points, line, area, lo, hi };
  }

  const helpers = { normalizeBase, formatPeriod, formatTimestamp, chartGeometry, METRICS };
  if (typeof module === "object" && module.exports) module.exports = helpers;
  if (typeof document === "undefined" || !document.getElementById("live")) return;

  // ---- browser part ----------------------------------------------------------
  const $ = (id) => document.getElementById(id);
  const els = {
    form: $("live-form"), api: $("live-api"), well: $("live-well"), granularity: $("live-granularity"),
    metric: $("live-metric"), state: $("live-state"), message: $("live-message"),
    snapshot: $("live-snapshot"), published: $("live-published"), rows: $("live-rows"), checked: $("live-checked"),
    line: $("live-line"), area: $("live-area"), dots: $("live-dots"), grid: $("live-grid-labels"),
    axis: $("live-axis"), value: $("live-value"), valueLabel: $("live-value-label"),
    tbody: $("live-tbody"), empty: $("live-empty"),
  };

  const view = { well: null, granularity: "hourly", metric: "avg_pressure_bar" };
  let base = initialBase();
  let controller = null;
  let connected = false;
  let saveOnSuccess = false; // only an address the user typed is remembered, never ?api=

  function readStored() {
    try { return window.localStorage.getItem(STORAGE_KEY); } catch { return null; }
  }
  function writeStored(value) {
    try { window.localStorage.setItem(STORAGE_KEY, value); } catch { /* storage may be blocked */ }
  }
  function initialBase() {
    const fromQuery = normalizeBase(new URLSearchParams(window.location.search).get("api"));
    return fromQuery || normalizeBase(readStored()) || DEFAULT_API;
  }

  function setState(kind, text, help) {
    const labels = { connecting: "CONNECTING", connected: "CONNECTED", waiting: "WAITING", offline: "OFFLINE", error: "ERROR" };
    els.state.textContent = labels[kind];
    els.state.classList.toggle("warning", kind !== "connected" && kind !== "connecting");
    els.message.textContent = text || "";
    els.message.hidden = !text;
    if (help) els.message.append(document.createElement("br"), Object.assign(document.createElement("code"), { textContent: help }));
  }

  class ApiError extends Error {
    constructor(status) { super(`HTTP ${status}`); this.status = status; }
  }

  async function getJson(path, params, signal) {
    const url = new URL(base + path);
    Object.entries(params || {}).forEach(([k, v]) => v !== undefined && url.searchParams.set(k, v));
    const response = await fetch(url, { signal, headers: { Accept: "application/json" } });
    if (!response.ok) throw new ApiError(response.status);
    return response.json();
  }

  async function fetchMart(signal) {
    const path = `/api/v1/marts/${view.granularity}`;
    const params = { well_id: view.well, limit: MAX_ROWS };
    let page = await getJson(path, params, signal);
    if (page.total > MAX_ROWS) page = await getJson(path, { ...params, offset: page.total - MAX_ROWS }, signal);
    return page;
  }

  async function refresh() {
    if (controller) controller.abort();
    const current = new AbortController();
    controller = current;
    let timedOut = false;
    const timer = window.setTimeout(() => { timedOut = true; current.abort(); }, TIMEOUT_MS);
    if (!connected) setState("connecting", `Connecting to ${base} …`);
    try {
      const wells = await getJson("/api/v1/wells", null, current.signal);
      fillWells(wells.wells);
      if (!wells.wells.length) throw new ApiError(503);
      const page = await fetchMart(current.signal);
      connected = true;
      if (saveOnSuccess) { writeStored(base); saveOnSuccess = false; }
      renderPage(page, wells.snapshot_id);
      setState("connected");
    } catch (error) {
      if (controller !== current || (error.name === "AbortError" && !timedOut)) return;
      connected = false;
      clearChart();
      if (error instanceof ApiError && error.status === 503) {
        setState("waiting", "The API is up, but no snapshot has been published yet.", "make up && docker compose run --rm cli publish --scenario normal --count 96");
      } else if (error instanceof ApiError) {
        setState("error", `The API answered ${error.status}.`);
      } else {
        setState("offline", `Cannot reach ${base}${timedOut ? " (timed out)" : ""}. The playground above stays a simulation.`, "make api");
      }
    } finally {
      window.clearTimeout(timer);
    }
  }

  function fillWells(names) {
    const existing = Array.from(els.well.options).map((o) => o.value);
    if (existing.join() !== names.join()) {
      els.well.replaceChildren(...names.map((name) => new Option(name, name)));
    }
    if (!names.includes(view.well)) view.well = names[0] || null;
    els.well.value = view.well || "";
    els.well.disabled = !names.length;
  }

  function clearChart() {
    els.line.setAttribute("points", "");
    els.area.setAttribute("d", "");
    els.dots.replaceChildren();
    els.grid.replaceChildren();
    els.axis.replaceChildren();
    els.tbody.replaceChildren();
    els.value.textContent = "—";
    els.empty.hidden = false;
  }

  function svgText(x, y, text) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", "text");
    node.setAttribute("x", x);
    node.setAttribute("y", y);
    node.textContent = text;
    return node;
  }

  function renderPage(page, snapshotId) {
    const metric = METRICS[view.metric];
    els.snapshot.textContent = snapshotId;
    els.published.textContent = formatTimestamp(page.published_at);
    els.rows.textContent = String(page.total);
    els.checked.textContent = new Date().toLocaleTimeString();
    els.valueLabel.textContent = `${metric.label} · latest period`;

    const geometry = chartGeometry(page.items, view.metric);
    els.empty.hidden = Boolean(geometry);
    if (!geometry) { clearChart(); return; }

    els.line.setAttribute("points", geometry.line);
    els.area.setAttribute("d", geometry.area);
    const last = geometry.points[geometry.points.length - 1];
    els.value.textContent = `${last.value.toFixed(1)} ${metric.unit}`;

    const dots = geometry.points.map((p, index) => {
      const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      const isLast = index === geometry.points.length - 1;
      dot.setAttribute("cx", p.x);
      dot.setAttribute("cy", p.y);
      dot.setAttribute("r", isLast ? 6 : 3);
      dot.setAttribute("class", isLast ? "chart-point aqua-point" : "chart-dot");
      const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
      title.textContent = `${formatPeriod(p.item.period_start, view.granularity)} UTC: ${p.value.toFixed(2)} ${metric.unit}`;
      dot.append(title);
      return dot;
    });
    els.dots.replaceChildren(...dots);
    els.grid.replaceChildren(
      svgText(0, 28, `${geometry.hi.toFixed(1)} ${metric.unit}`),
      svgText(0, 214, `${geometry.lo.toFixed(1)} ${metric.unit}`),
    );
    const first = page.items[0];
    const final = page.items[page.items.length - 1];
    const labels = [first, final].map((i) => formatPeriod(i.period_start, view.granularity));
    els.axis.replaceChildren(...(page.items.length > 1 ? labels : labels.slice(0, 1)).map((t) => Object.assign(document.createElement("span"), { textContent: t })));
    renderTable(page.items);
  }

  function renderTable(items) {
    const cell = (text) => Object.assign(document.createElement("td"), { textContent: text });
    const rows = items.slice().reverse().map((item) => {
      const tr = document.createElement("tr");
      tr.append(
        cell(formatPeriod(item.period_start, view.granularity)),
        cell(String(item.readings)),
        cell(item.avg_pressure_bar.toFixed(1)),
        cell(item.avg_temperature_c.toFixed(1)),
        cell(item.avg_flow_m3_h.toFixed(1)),
        cell(item.max_water_cut_pct.toFixed(1)),
      );
      return tr;
    });
    els.tbody.replaceChildren(...rows);
  }

  els.form.addEventListener("submit", (event) => {
    event.preventDefault();
    const next = normalizeBase(els.api.value);
    if (!next) { setState("error", "Enter an http:// or https:// address, for example http://localhost:8000."); return; }
    base = next;
    els.api.value = base;
    saveOnSuccess = true;
    connected = false;
    refresh();
  });
  els.well.addEventListener("change", () => { view.well = els.well.value; refresh(); });
  els.granularity.addEventListener("change", () => { view.granularity = els.granularity.value; refresh(); });
  els.metric.addEventListener("change", () => { view.metric = els.metric.value; refresh(); });
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
  window.setInterval(() => { if (!document.hidden) refresh(); }, POLL_MS);

  els.api.value = base;
  clearChart();
  refresh();
})();
