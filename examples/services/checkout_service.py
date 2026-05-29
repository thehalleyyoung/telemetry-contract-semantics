"""Tiny example service with OpenTelemetry-style instrumentation names.

The imports are intentionally omitted so this file remains dependency-free; the
static checker only needs source literals to verify instrumentation coverage.
"""


def checkout(cart_id: str, tenant_id: str, provider: str) -> None:
    tracer = get_tracer("checkout")  # noqa: F821 - illustrative sample
    meter = get_meter("checkout")  # noqa: F821 - illustrative sample
    logger = get_logger("checkout")  # noqa: F821 - illustrative sample

    with tracer.start_as_current_span("checkout.request") as request_span:
        request_span.set_attribute("tenant_id", tenant_id)
        request_span.set_attribute("cart_id", cart_id)
        request_span.set_attribute("result", "failed")
        counter = meter.create_counter("checkout.requests.total")
        counter.add(1, {"tenant_id": tenant_id, "result": "failed"})

        with tracer.start_as_current_span("payment.authorize") as payment_span:
            payment_span.set_attribute("payment_provider", provider)
            payment_span.set_attribute("retry_count", 2)
            histogram = meter.create_histogram("payment.authorization.latency_ms")
            histogram.record(812.7, {"payment_provider": provider})
            logger.error(
                "payment authorization failed after retries",
                extra={"event_name": "checkout.payment_failed", "tenant_id": tenant_id, "cart_id": cart_id, "error_code": "PAYMENT_TIMEOUT"},
            )
