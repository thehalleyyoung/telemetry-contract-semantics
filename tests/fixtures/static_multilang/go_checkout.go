package checkout

func instrument() {
	spanName := "checkout.go_submit"
	tracer.Start(ctx, spanName)
	meter.Int64Counter("checkout.go_requests")
	log.Error("checkout go failure", "event_name", "checkout.go_failure", "trace_id", traceID)
}
