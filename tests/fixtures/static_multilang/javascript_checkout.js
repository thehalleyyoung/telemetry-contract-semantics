const spanPrefix = "checkout.";
const metricSuffix = "latency_ms";
const eventName = "checkout.failure";
tracer.startSpan(spanPrefix + "browser_submit");
meter.createHistogram(`${spanPrefix}${metricSuffix}`, { unit: "ms", description: "checkout latency" });
logger.error("checkout failure", { event_name: eventName, trace_id: traceId, retryable: true });
