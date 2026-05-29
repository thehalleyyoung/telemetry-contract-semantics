from opentelemetry import trace
import logging

tracer = trace.get_tracer("public_static_patterns")
meter = trace.get_tracer_provider().meter_provider.get_meter("public_static_patterns")
logger = logging.getLogger(__name__)
login_attempts = meter.create_counter("auth.login_attempts")


def login(request):
    with tracer.start_as_current_span("auth.login.error") as span:
        span.set_attribute("retryable", True)
        logger.error("login failed password=%s raw_payload=%s", request.password, request.body_preview)
        login_attempts.add(1, attributes={"user_id": request.user_id, "path": request.path})
