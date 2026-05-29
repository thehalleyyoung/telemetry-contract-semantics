# Responsible disclosure workflow

Telemetry Contracts is defensive tooling. When using it on third-party or production telemetry:

1. Minimize data before import; prefer synthetic, redacted, or sampled captures.
2. Do not publish raw secrets, tokens, PII, private URLs, customer identifiers, or proprietary source snippets.
3. Record finding evidence as stable finding codes, paths, redacted previews, hashes, and reproduction commands.
4. For public-code case studies, pin source URLs, commits, retrieval dates, license notes, and generated reports.
5. For potential vulnerabilities or sensitive telemetry leaks, notify the affected project or owner privately first.
6. Give maintainers enough context to reproduce without exposing unrelated data.
7. Coordinate publication timing and clearly label reconstructed fixtures as reconstructed.
8. Treat static findings as review leads unless confirmed by maintainers or runtime evidence.

Reports in this repository should stay reproducible, bounded, and privacy-preserving.
