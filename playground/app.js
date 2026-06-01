"use strict";

// Zero-install playground glue. Boots Pyodide, loads the pure-stdlib engine
// bundle, and runs `telemetry_contracts.playground.analyze_text` entirely client
// side. Results are shareable via a URL hash (no server).

const els = {
  input: document.getElementById("input"),
  service: document.getElementById("service"),
  analyze: document.getElementById("analyze"),
  share: document.getElementById("share"),
  status: document.getElementById("status"),
  results: document.getElementById("results"),
  examples: document.getElementById("examples"),
};

let pyodide = null;

function setStatus(msg) {
  els.status.textContent = msg || "";
}

function scoreColor(score) {
  if (score === null || score === undefined) return "#8b949e";
  if (score >= 90) return "#3fb950";
  if (score >= 75) return "#56b34a";
  if (score >= 60) return "#a4a61d";
  if (score >= 40) return "#d29922";
  if (score >= 20) return "#db6d28";
  return "#f85149";
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// --- shareable state via URL hash (base64-encoded JSON, no server) ----------

function encodeState(text, service) {
  const payload = JSON.stringify({ t: text, s: service || "" });
  return btoa(unescape(encodeURIComponent(payload)));
}

function decodeState(hash) {
  try {
    const payload = decodeURIComponent(escape(atob(hash)));
    const obj = JSON.parse(payload);
    return { text: obj.t || "", service: obj.s || "" };
  } catch (e) {
    return null;
  }
}

function updateShareLink() {
  const encoded = encodeState(els.input.value, els.service.value);
  const url = `${location.origin}${location.pathname}#${encoded}`;
  history.replaceState(null, "", `#${encoded}`);
  return url;
}

// --- engine boot ------------------------------------------------------------

async function boot() {
  setStatus("Loading the analysis engine (Pyodide)…");
  pyodide = await loadPyodide();
  setStatus("Loading the telemetry-contracts engine…");
  const resp = await fetch("assets/telemetry_contracts.zip");
  const buf = await resp.arrayBuffer();
  pyodide.unpackArchive(buf, "zip");
  // Warm the import so the first analysis is fast.
  await pyodide.runPythonAsync("import telemetry_contracts.playground as _p");
  els.analyze.disabled = false;
  els.analyze.textContent = "Analyze";
  els.share.disabled = false;
  setStatus("Ready. Paste telemetry or pick an example, then Analyze.");
}

async function loadExamples() {
  try {
    const resp = await fetch("assets/examples.json");
    const examples = await resp.json();
    for (const ex of examples) {
      const btn = document.createElement("button");
      btn.textContent = ex.title;
      btn.title = ex.description;
      btn.addEventListener("click", async () => {
        const r = await fetch(`assets/${ex.file}`);
        els.input.value = await r.text();
        els.service.value = ex.service || "";
        updateShareLink();
        if (!els.analyze.disabled) runAnalysis();
      });
      els.examples.appendChild(btn);
    }
  } catch (e) {
    // Non-fatal: examples are a convenience.
  }
}

// --- analysis ---------------------------------------------------------------

async function runAnalysis() {
  if (!pyodide) return;
  const text = els.input.value;
  if (!text.trim()) {
    setStatus("Paste some telemetry first.");
    return;
  }
  setStatus("Analyzing…");
  els.analyze.disabled = true;
  try {
    pyodide.globals.set("input_text", text);
    pyodide.globals.set("input_service", els.service.value || null);
    const json = await pyodide.runPythonAsync(`
import json
from telemetry_contracts.playground import analyze_text
json.dumps(analyze_text(input_text, service=(input_service or None)), sort_keys=True)
`);
    renderReport(JSON.parse(json));
    updateShareLink();
    setStatus("Done. Tip: use “Copy share link” to share this result.");
  } catch (e) {
    setStatus("Could not analyze that input. Check the format and try again.");
    console.error(e);
  } finally {
    els.analyze.disabled = false;
  }
}

function renderReport(report) {
  const score = report.diagnosability_score;
  const color = scoreColor(report.has_telemetry ? score : null);
  const scoreText = report.has_telemetry ? `${score}` : "—";

  const parts = [];
  parts.push(`
    <div class="scorecard">
      <div class="score-dial" style="color:${color}">
        ${scoreText}<small>${report.has_telemetry ? "/ 100" : "no telemetry"}</small>
      </div>
      <div>
        <div class="verdict">${escapeHtml(report.verdict)}
          <span class="sub">${report.event_count} event(s) parsed as <span class="code">${escapeHtml(report.format)}</span></span>
        </div>
      </div>
    </div>
  `);

  if (report.unanswered_questions.length) {
    parts.push("<h2>Questions you can’t answer yet</h2><ul class='question-list'>");
    for (const q of report.unanswered_questions) {
      parts.push(`<li>${escapeHtml(q.question)}${q.gap ? ` <span class='code'>(${escapeHtml(q.gap)})</span>` : ""}</li>`);
    }
    parts.push("</ul>");
  }

  if (report.top_gaps.length) {
    parts.push("<h2>Top gaps</h2><ul class='gap-list'>");
    for (const g of report.top_gaps) {
      parts.push(`<li><span class="code">${escapeHtml(g.code)}</span><span class="count-pill">${g.count}×</span></li>`);
    }
    parts.push("</ul>");
  }

  if (report.findings.length) {
    parts.push("<h2>Findings</h2><ul class='finding-list'>");
    for (const f of report.findings) {
      const sev = f.severity || "info";
      parts.push(
        `<li><span class="sev sev-${escapeHtml(sev)}">${escapeHtml(sev)}</span><span class="code">${escapeHtml(f.code)}</span><br/>${escapeHtml(f.message)}</li>`,
      );
    }
    parts.push("</ul>");
  }

  if (!report.unanswered_questions.length && !report.top_gaps.length && !report.findings.length) {
    parts.push("<h2>No gaps detected 🎉</h2><p>This telemetry can answer the standard incident questions.</p>");
  }

  els.results.innerHTML = parts.join("");
  els.results.hidden = false;
}

// --- wiring -----------------------------------------------------------------

els.analyze.addEventListener("click", runAnalysis);
els.input.addEventListener("input", updateShareLink);
els.service.addEventListener("input", updateShareLink);
els.share.addEventListener("click", async () => {
  const url = updateShareLink();
  try {
    await navigator.clipboard.writeText(url);
    setStatus("Share link copied to clipboard.");
  } catch (e) {
    setStatus(url);
  }
});

// Restore shared state from the URL hash, if any.
if (location.hash.length > 1) {
  const restored = decodeState(location.hash.slice(1));
  if (restored) {
    els.input.value = restored.text;
    els.service.value = restored.service;
  }
}

loadExamples();
boot().then(() => {
  if (els.input.value.trim()) runAnalysis();
});
