fn instrument() {
    let span_name = "checkout.rust_submit";
    tracer.start_span(span_name);
    meter.u64_counter("checkout.rust_requests").build();
    log::error!(event_name = "checkout.rust_failure", trace_id = %trace_id, "checkout rust failure");
}
