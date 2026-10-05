const test = require("node:test");
const assert = require("node:assert/strict");
const { normalizeBase, formatPeriod, formatTimestamp, chartGeometry } = require("../../docs/live.js");

test("normalizeBase accepts http(s) addresses and trims trailing slashes", () => {
  assert.equal(normalizeBase("http://localhost:8000/"), "http://localhost:8000");
  assert.equal(normalizeBase("  https://api.example.com/base//  "), "https://api.example.com/base");
});

test("normalizeBase drops query, hash and rejects unsafe or invalid input", () => {
  assert.equal(normalizeBase("http://localhost:8000/?x=1#h"), "http://localhost:8000");
  for (const bad of ["javascript:alert(1)", "ftp://host", "localhost:8000", "", "   ", null, undefined, 42,
    "http://user:pass@host/"]) {
    assert.equal(normalizeBase(bad), null, String(bad));
  }
});

test("period labels are rendered in UTC", () => {
  assert.equal(formatPeriod("2026-10-01T10:00:00Z", "hourly"), "Oct 1, 10:00");
  assert.equal(formatPeriod("2026-10-01T23:00:00-05:00", "hourly"), "Oct 2, 04:00");
  assert.equal(formatPeriod("2026-10-01T10:00:00Z", "daily"), "Oct 1");
  assert.equal(formatPeriod("garbage", "daily"), "garbage");
  assert.equal(formatTimestamp("2026-10-04T18:42:25.217275Z"), "2026-10-04 18:42:25 UTC");
});

const rows = (values) => values.map((v, i) => ({
  period_start: new Date(Date.UTC(2026, 9, 1, i)).toISOString(), avg_pressure_bar: v,
}));

test("chartGeometry returns null for no data", () => {
  assert.equal(chartGeometry([], "avg_pressure_bar"), null);
});

test("chartGeometry maps min to the bottom grid line and max to the top", () => {
  const g = chartGeometry(rows([80, 100, 90]), "avg_pressure_bar");
  assert.equal(g.points[0].y, 222);
  assert.equal(g.points[1].y, 36);
  assert.ok(g.points[0].x < g.points[1].x && g.points[1].x < g.points[2].x);
  assert.equal(g.lo, 80);
  assert.equal(g.hi, 100);
  assert.match(g.area, /^M.* Z$/);
});

test("chartGeometry spaces points by time, not by index", () => {
  const items = [0, 1, 5].map((h, i) => ({
    period_start: new Date(Date.UTC(2026, 9, 1, h)).toISOString(), avg_pressure_bar: 80 + i,
  }));
  const [a, b, c] = chartGeometry(items, "avg_pressure_bar").points;
  assert.ok(Math.abs((b.x - a.x) / (c.x - b.x) - 1 / 4) < 1e-9);
});

test("a single point or a flat series stays inside the chart", () => {
  const single = chartGeometry(rows([90]), "avg_pressure_bar");
  assert.equal(single.points[0].x, 350);
  const flat = chartGeometry(rows([90, 90, 90]), "avg_pressure_bar");
  for (const p of flat.points) assert.ok(p.y > 36 && p.y < 222 && Number.isFinite(p.y));
});
