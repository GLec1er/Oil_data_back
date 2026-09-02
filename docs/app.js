(() => {
  const defaults = {
    pressure: 84.6,
    temperature: 72,
    flow: 128,
    "water-cut": 18,
    well: "NORTH-07",
  };

  const inputs = ["pressure", "temperature", "flow", "water-cut"].map((id) => document.getElementById(id));
  const outputs = Object.fromEntries(inputs.map((input) => [input.id, document.getElementById(`${input.id}-output`)]));
  const payload = document.getElementById("payload");
  const state = document.getElementById("signal-state");
  const health = document.getElementById("health-score");
  const trend = document.getElementById("trend-value");
  const trendCopy = document.getElementById("trend-copy");
  const labLine = document.getElementById("lab-line");
  const labArea = document.getElementById("lab-area");
  const labPoint = document.getElementById("lab-point");

  function formatValue(input) {
    const value = Number(input.value);
    const decimals = input.id === "pressure" ? 1 : 0;
    return `${value.toFixed(decimals)} ${input.dataset.unit}`;
  }

  function setSliderProgress(input) {
    const min = Number(input.min);
    const max = Number(input.max);
    const progress = ((Number(input.value) - min) / (max - min)) * 100;
    input.style.setProperty("--range-progress", `${progress}%`);
  }

  function buildPoints(values) {
    const pressure = Number(values.pressure);
    const temperature = Number(values.temperature);
    const flow = Number(values.flow);
    const waterCut = Number(values["water-cut"]);
    const variance = (pressure - 84.6) * 0.42 + (temperature - 72) * 0.12 + (flow - 128) * 0.045 - (waterCut - 18) * 0.1;
    const base = [190, 176, 187, 146, 156, 127, 140, 98, 112, 78, 93, 57, 72];
    return base.map((point, index) => {
      const wave = Math.sin(index * 1.7 + pressure / 24) * (3 + Math.abs(variance) * 0.16);
      return Math.max(34, Math.min(223, point - variance * (index / 12) + wave));
    });
  }

  function render() {
    const values = Object.fromEntries(inputs.map((input) => [input.id, Number(input.value)]));
    const well = document.getElementById("well").value;
    inputs.forEach((input) => {
      outputs[input.id].textContent = formatValue(input);
      setSliderProgress(input);
    });

    const points = buildPoints(values);
    const pointsString = points.map((point, index) => `${index * (700 / 12)},${point}`).join(" ");
    labLine.setAttribute("points", pointsString);
    labArea.setAttribute("d", `M0 ${points[0]} ${points.map((point, index) => `L${index * (700 / 12)} ${point}`).join(" ")} L700 260 L0 260 Z`);
    labPoint.setAttribute("cx", `${11 * (700 / 12)}`);
    labPoint.setAttribute("cy", `${points[11]}`);

    const risk = Math.abs(values.pressure - 85) * 0.22 + Math.abs(values.temperature - 72) * 0.08 + Math.abs(values.flow - 128) * 0.025 + values["water-cut"] * 0.14;
    const score = Math.max(58, Math.min(99, Math.round(97 - risk)));
    const trendValue = ((values.pressure - 80) / 4 + (values.flow - 120) / 20 - (values["water-cut"] - 14) / 5).toFixed(1);
    const isWarning = score < 76 || values["water-cut"] > 42;
    health.textContent = score;
    trend.textContent = `${Number(trendValue) >= 0 ? "+" : ""}${trendValue}%`;
    trendCopy.textContent = isWarning ? "needs attention" : "within expected range";
    state.textContent = isWarning ? "ATTENTION" : "STABLE";
    state.classList.toggle("warning", isWarning);

    payload.innerHTML = `<code>${JSON.stringify({
      well_id: well,
      pressure_bar: Number(values.pressure.toFixed(1)),
      temperature_c: values.temperature,
      flow_m3_h: values.flow,
      water_cut_pct: values["water-cut"],
    }, null, 2)}</code>`;
  }

  function reset() {
    inputs.forEach((input) => { input.value = defaults[input.id]; });
    document.getElementById("well").value = defaults.well;
    render();
  }

  async function copyPayload() {
    const text = payload.textContent;
    const status = document.getElementById("copy-status");
    try {
      await navigator.clipboard.writeText(text);
      status.textContent = "Copied";
    } catch {
      status.textContent = "Select the JSON to copy";
    }
    window.setTimeout(() => { status.textContent = ""; }, 1800);
  }

  inputs.forEach((input) => input.addEventListener("input", render));
  document.getElementById("well").addEventListener("change", render);
  document.getElementById("reset-lab").addEventListener("click", reset);
  document.getElementById("copy-payload").addEventListener("click", copyPayload);
  render();
})();
