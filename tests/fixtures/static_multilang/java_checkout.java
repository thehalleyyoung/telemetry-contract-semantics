class CheckoutTelemetry {
  void instrument() {
    String spanName = "checkout.java_submit";
    tracer.spanBuilder(spanName).startSpan();
    meter.counterBuilder("checkout.java_requests").setUnit("1").setDescription("requests").build();
    logger.error("checkout java failure", kv("event_name", "checkout.java_failure"), kv("trace_id", traceId));
  }
}
