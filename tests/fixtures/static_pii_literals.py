def log_literal_pii(logger):
    logger.error("signup failed email=casey@example.com phone=+1 415 555 0199 tenant_id=tenant-123")


def log_plain_date(logger):
    logger.info("daily job completed date=2026-05-29")
