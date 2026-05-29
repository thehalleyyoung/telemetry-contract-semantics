# OWASP SecureTea Signin.js current-impact case study

This case study runs the static telemetry/privacy scanner against a public source file from OWASP SecureTea Project. It is defensive analysis of public sample code, not a vulnerability disclosure or exploit guide.

- Source: <https://github.com/OWASP/SecureTea-Project/blob/7a2da8756e6addbe379ae9b23905dcdbe68b3814/react_gui/src/views/Signin.js>
- Retrieval date: 2026-05-29
- License: MIT; see `LICENSE.SecureTea.md`.

Reproduce via:

```bash
python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --format json --output reports/current_impact.json
python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --format markdown --output reports/current_impact.md
```
