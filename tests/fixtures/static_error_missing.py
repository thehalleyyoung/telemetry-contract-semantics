ERROR_SPAN = "checkout.error"

def instrument(tracer, exc):
    with tracer.start_as_current_span(ERROR_SPAN) as span:
        span.set_attribute("exception.type", type(exc).__name__)
