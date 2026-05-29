class CheckoutTelemetry {
  void Instrument() {
    var spanName = "checkout.csharp_submit";
    activitySource.StartActivity(spanName);
    meter.CreateCounter<long>("checkout.csharp_requests", unit: "1", description: "requests");
    logger.LogError("checkout csharp failure {event_name} {trace_id}", "checkout.csharp_failure", traceId);
  }
}
