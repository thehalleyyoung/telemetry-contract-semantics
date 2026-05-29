# Synthetic microservices benchmark fixture

This fixture models a checkout request crossing checkout, payment, inventory, shipping, auth, notification, queue, cache, database, and collector contracts. It is synthetic and public: the goal is to validate cross-service contract loading, correlation-key consistency, scenario handoff evidence, and benchmark accounting without asserting any real incident.

Run it with:

```bash
python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --case-id synthetic-microservices-checkout-pass --format markdown
```
