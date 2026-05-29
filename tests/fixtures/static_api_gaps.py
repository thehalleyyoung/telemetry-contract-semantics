SPAN_NAME = "checkout.request"
METRIC_NAME = "checkout.requests"

def instrument(tracer, meter):
    with tracer.start_as_current_span(SPAN_NAME):
        pass
    meter.create_counter(METRIC_NAME)
