/* ============================================================
   Front-end: consume la API y renderiza sugerencias + estadísticas.
   Sin dependencias ni build: JS puro (ES modules no requeridos).
   ============================================================ */
"use strict";

const $ = (sel) => document.querySelector(sel);

const els = {
  select: $("#lottery-select"),
  predictBtn: $("#predict-btn"),
  refreshBtn: $("#refresh-btn"),
  status: $("#status-line"),
  results: $("#results"),
  suggestions: $("#suggestions"),
  drawsUsed: $("#draws-used"),
  lastDraw: $("#last-draw"),
  hotList: $("#hot-list"),
  coldList: $("#cold-list"),
  heatmap: $("#heatmap"),
  windowLabel: $("#window-label"),
  disclaimerText: $("#disclaimer-text"),
  footerDisclaimer: $("#footer-disclaimer"),
  spinner: $("#predict-btn .spinner"),
  btnLabel: $("#predict-btn .btn-label"),
  daysChip: $("#days-chip"),
  drawDays: $("#draw-days"),
  statsCifras4: $("#stats-cifras4"),
  statsBaloto: $("#stats-baloto"),
  ballsGrid: $("#balls-grid"),
  superGrid: $("#super-grid"),
  search: $("#lottery-search"),
  searchEmpty: $("#search-empty"),
  refreshAllBtn: $("#refresh-all-btn"),
};

// Catálogo completo en memoria (para filtrar sin volver a pedir al servidor).
let allLotteries = [];

const POSITION_LABELS = ["Millar", "Centena", "Decena", "Unidad"];

function setStatus(msg, kind = "") {
  els.status.textContent = msg || "";
  els.status.className = "status-line" + (kind ? " " + kind : "");
}

function setLoading(loading) {
  els.predictBtn.disabled = loading;
  els.refreshBtn.disabled = loading;
  els.spinner.hidden = !loading;
  els.btnLabel.textContent = loading ? "Analizando…" : "Obtener predicción del día";
}

async function loadLotteries() {
  try {
    const res = await fetch("/api/lotteries");
    const data = await res.json();
    els.windowLabel.textContent = data.window;
    if (data.disclaimer) {
      els.disclaimerText.textContent = data.disclaimer;
      els.footerDisclaimer.textContent = data.disclaimer;
    }
    allLotteries = data.lotteries;
    renderSelect();
  } catch (err) {
    setStatus("No se pudo cargar el catálogo de loterías.", "error");
  }
}

// Dibuja el <select> agrupado, aplicando el texto de búsqueda como filtro.
function renderSelect() {
  const q = (els.search.value || "").trim().toLowerCase();
  const prev = els.select.value;
  const matches = allLotteries.filter(
    (lot) =>
      !q ||
      lot.name.toLowerCase().includes(q) ||
      lot.group.toLowerCase().includes(q)
  );

  const groups = {};
  for (const lot of matches) {
    (groups[lot.group] = groups[lot.group] || []).push(lot);
  }
  els.select.innerHTML = "";
  for (const [group, items] of Object.entries(groups)) {
    const og = document.createElement("optgroup");
    og.label = group;
    for (const lot of items) {
      const opt = document.createElement("option");
      opt.value = lot.slug;
      opt.textContent = `${lot.name} (${lot.stored} sorteos)`;
      og.appendChild(opt);
    }
    els.select.appendChild(og);
  }

  // Conservar selección previa si sigue visible.
  if (matches.some((l) => l.slug === prev)) els.select.value = prev;
  els.searchEmpty.hidden = matches.length > 0;
  // Con búsqueda activa, mostrar varias filas para facilitar la elección.
  const nGroups = Object.keys(groups).length;
  els.select.size = q && matches.length > 1 ? Math.min(matches.length + nGroups, 10) : 1;
}

async function refreshData() {
  const slug = els.select.value;
  if (!slug) return;
  setLoading(true);
  setStatus("Actualizando datos desde las fuentes públicas…");
  try {
    const res = await fetch(`/api/refresh/${slug}`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Error al actualizar");
    setStatus(
      `Listo: ${data.inserted} nuevos · ${data.total_stored} sorteos almacenados` +
        (data.sources_used.length ? ` (fuentes: ${data.sources_used.join(", ")})` : ""),
      "ok"
    );
    await loadLotteries();
    els.select.value = slug;
  } catch (err) {
    setStatus(err.message || "Error al actualizar datos.", "error");
  } finally {
    setLoading(false);
  }
}

async function predict() {
  const slug = els.select.value;
  if (!slug) return;
  setLoading(true);
  setStatus("Estudiando el histórico y calculando probabilidades…");
  try {
    const res = await fetch(`/api/predict/${slug}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Error al predecir");
    render(data);
    setStatus("", "");
    els.results.hidden = false;
    els.results.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    setStatus(err.message || "Error al obtener la predicción.", "error");
  } finally {
    setLoading(false);
  }
}

function render(data) {
  // --- Sugerencias ---
  els.suggestions.innerHTML = "";
  const maxScore = Math.max(...data.suggestions.map((s) => s.score), 0.0001);
  const cardKind = data.kind === "baloto" ? " baloto" : "";
  data.suggestions.forEach((s, i) => {
    const card = document.createElement("div");
    card.className = "suggestion-card" + cardKind;
    card.style.animationDelay = `${i * 0.08}s`;
    const pct = Math.round((s.score / maxScore) * 100);
    card.innerHTML = `
      <div class="suggestion-rank">Sugerencia ${i + 1}</div>
      <div class="suggestion-number">${s.number}</div>
      <div class="suggestion-method">${s.method}</div>
      <div class="suggestion-rationale">${s.rationale}</div>
      <div class="suggestion-score">
        Respaldo relativo: ${(s.score * 100).toFixed(1)}%
        <div class="bar"><span style="width:${pct}%"></span></div>
      </div>`;
    els.suggestions.appendChild(card);
  });

  // --- Meta ---
  els.drawsUsed.textContent = data.draws_used;
  let lastTxt = data.last_draw || "—";
  if (data.last_extra) lastTxt += ` · ${data.last_extra}`;
  els.lastDraw.textContent = lastTxt;
  if (data.draw_days) {
    els.drawDays.textContent = data.draw_days;
    els.daysChip.hidden = false;
  } else {
    els.daysChip.hidden = true;
  }

  // --- Estadísticas según el tipo de lotería ---
  const isBaloto = data.kind === "baloto";
  els.statsCifras4.hidden = isBaloto;
  els.statsBaloto.hidden = !isBaloto;

  if (isBaloto) {
    renderBalls(els.ballsGrid, data.ball_stats);
    renderBalls(els.superGrid, data.superball_stats);
  } else {
    renderFreq(els.hotList, data.hot_numbers, "hot");
    renderFreq(els.coldList, data.cold_numbers, "cold");
    renderHeatmap(data.position_stats);
  }
}

function renderBalls(container, stats) {
  container.innerHTML = "";
  const max = Math.max(...stats.map((b) => b.count), 1);
  for (const b of stats) {
    const cell = document.createElement("div");
    cell.className = "ball";
    const intensity = b.count / max;
    const alpha = 0.15 + intensity * 0.85;
    cell.style.background = `rgba(124, 92, 255, ${alpha.toFixed(2)})`;
    cell.innerHTML = `<span class="ball-n">${String(b.number).padStart(2, "0")}</span><span class="ball-c">${b.count}</span>`;
    cell.title = `Balota ${b.number}: ${b.count} veces`;
    container.appendChild(cell);
  }
}

function renderFreq(container, items, kind) {
  container.innerHTML = "";
  const max = Math.max(...items.map((it) => it[1]), 1);
  for (const [num, count] of items) {
    const row = document.createElement("div");
    row.className = `freq-row ${kind}`;
    const w = Math.round((count / max) * 100);
    row.innerHTML = `
      <div class="freq-num">${num}</div>
      <div class="freq-bar"><span style="width:${w}%"></span></div>
      <div class="freq-count">${count}</div>`;
    container.appendChild(row);
  }
  if (!items.length) container.innerHTML = '<p class="panel-hint">Sin datos.</p>';
}

function renderHeatmap(positionStats) {
  els.heatmap.innerHTML = "";
  for (const stat of positionStats) {
    const max = Math.max(...stat.counts, 1);
    const row = document.createElement("div");
    row.className = "heat-row";
    const label = document.createElement("div");
    label.className = "heat-label";
    label.textContent = POSITION_LABELS[stat.position] || `Pos ${stat.position}`;
    const cells = document.createElement("div");
    cells.className = "heat-cells";
    for (let d = 0; d < 10; d++) {
      const cell = document.createElement("div");
      cell.className = "heat-cell";
      const intensity = stat.counts[d] / max; // 0..1
      // color: interpola de fondo a acento
      const alpha = 0.12 + intensity * 0.88;
      cell.style.background = `rgba(124, 92, 255, ${alpha.toFixed(2)})`;
      if (d === stat.top_digit) cell.style.boxShadow = "0 0 0 2px var(--accent-2) inset";
      cell.innerHTML = `<span class="d">${d}</span>${stat.counts[d]}`;
      cell.title = `Dígito ${d}: ${stat.counts[d]} veces en ${label.textContent}`;
      cells.appendChild(cell);
    }
    row.appendChild(label);
    row.appendChild(cells);
    els.heatmap.appendChild(row);
  }
}

async function refreshAll() {
  setLoading(true);
  els.refreshAllBtn.disabled = true;
  setStatus("Actualizando todas las loterías… esto puede tardar un poco.");
  try {
    const res = await fetch("/api/refresh-all", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Error al actualizar");
    const errTxt = data.errors.length ? ` · ${data.errors.length} con error` : "";
    setStatus(
      `Listo: ${data.total_inserted} sorteos nuevos en ${data.lotteries_updated} loterías${errTxt}.`,
      "ok"
    );
    const prev = els.select.value;
    await loadLotteries();
    if (prev) els.select.value = prev;
  } catch (err) {
    setStatus(err.message || "Error al actualizar todas.", "error");
  } finally {
    els.refreshAllBtn.disabled = false;
    setLoading(false);
  }
}

els.predictBtn.addEventListener("click", predict);
els.refreshBtn.addEventListener("click", refreshData);
els.refreshAllBtn.addEventListener("click", refreshAll);
els.search.addEventListener("input", renderSelect);

loadLotteries();
