def audit(logger, event, token, email, phone, tenant_id):
    logger.error("auth.audit failed token=%s email=%s phone=%s tenant_id=%s payload_preview=%s", token, email, phone, tenant_id, event.get("raw_payload"))
