SPAN_NAME = "checkout.ruby_submit"
tracer.in_span(SPAN_NAME) do |span|
  meter.create_counter("checkout.ruby_requests")
  logger.error("checkout ruby failure", event_name: "checkout.ruby_failure", trace_id: trace_id)
end
