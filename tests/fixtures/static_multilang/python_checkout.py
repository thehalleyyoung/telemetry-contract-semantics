import logging

from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger(__name__)
SPAN_PREFIX = "checkout."
REQUEST_SUFFIX = "request"
ERROR_SPAN = f"{SPAN_PREFIX}error"
METRIC_PREFIX = "checkout"
EVENT_NAME = "checkout.error"
TRACER = trace.get_tracer("checkout.service")
METER = metrics.get_meter("checkout.service")


def instrument_checkout(tracer, meter, request_id, exc):
    requests = meter.create_counter(METRIC_PREFIX + ".requests", unit="1", description="checkout request count")
    requests.add(1, {"http.route": "/checkout", "request_id": request_id})
    with tracer.start_as_current_span(SPAN_PREFIX + REQUEST_SUFFIX) as span:
        span.set_attribute("http.route", "/checkout")
        span.set_attribute("request_id", request_id)
    with tracer.start_as_current_span(ERROR_SPAN) as span:
        span.record_exception(exc)
        span.set_status(Status(StatusCode.ERROR))
        span.set_attribute("exception.type", type(exc).__name__)
        span.set_attribute("remediation_hint", "retry after payment provider recovers")
        span.set_attribute("retryable", True)
        logger.error("checkout failed", extra={"event_name": EVENT_NAME, "trace_id": "abc", "request_id": request_id})
