// Pyodide smoke test for the browser playground engine.
//
// Loads the pure-stdlib engine bundle under Pyodide (the same way the browser
// playground does), then runs `analyze_text` on a known sample and asserts the
// diagnosability score and detected gap. This keeps the zero-install demo from
// rotting: if the engine ever stops importing or running under Pyodide, CI fails.
//
// Usage: node playground/smoke_test.mjs   (requires the `pyodide` npm package)

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { loadPyodide } from "pyodide";

const here = dirname(fileURLToPath(import.meta.url));

function assert(cond, msg) {
  if (!cond) {
    console.error("SMOKE FAIL:", msg);
    process.exit(1);
  }
}

const SAMPLE = [
  '{"kind":"span","name":"checkout.request","service":"checkout","status":"error","fields":{"tenant_id":"a"}}',
  '{"kind":"log","name":"checkout.error","service":"checkout","severity":"ERROR","fields":{"tenant_id":"a"}}',
].join("\n");

const pyodide = await loadPyodide();

const zipBytes = readFileSync(join(here, "assets", "telemetry_contracts.zip"));
pyodide.unpackArchive(zipBytes.buffer, "zip");

pyodide.globals.set("sample_text", SAMPLE);

const resultJson = await pyodide.runPythonAsync(`
import json
from telemetry_contracts.playground import analyze_text
report = analyze_text(sample_text)
json.dumps(report, sort_keys=True)
`);

const report = JSON.parse(resultJson);

assert(report.schema === "telemetry-contracts/playground@1", "unexpected schema");
assert(report.has_telemetry === true, "expected telemetry");
assert(typeof report.diagnosability_score === "number", "score not numeric");
assert(report.diagnosability_score >= 0 && report.diagnosability_score <= 100, "score out of range");
const gapCodes = report.top_gaps.map((g) => g.code);
assert(
  gapCodes.includes("telemetry.correlation_missing"),
  `expected correlation gap, got ${JSON.stringify(gapCodes)}`,
);

// Determinism: identical input must yield identical bytes under Pyodide too.
const resultJson2 = await pyodide.runPythonAsync(`
import json
from telemetry_contracts.playground import analyze_text
json.dumps(analyze_text(sample_text), sort_keys=True)
`);
assert(resultJson === resultJson2, "engine output not deterministic under Pyodide");

console.log(
  `SMOKE OK: engine ran under Pyodide; score=${report.diagnosability_score}, gaps=${JSON.stringify(gapCodes)}`,
);
