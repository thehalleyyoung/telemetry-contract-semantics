const prefix = "checkout.";
const spanName = `${prefix}typescript_submit`;
tracer.startSpan(spanName);
meter.createCounter(prefix + "typescript_requests", { unit: "1", description: "requests" });
console.warn("checkout ts warning", { eventName: "checkout.typescript_warning", requestId });
