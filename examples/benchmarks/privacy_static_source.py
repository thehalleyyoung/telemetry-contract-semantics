def signin(logger, meter, user_email, secret_password):
    logger.error("auth.failure invalid password=%s email=%s", secret_password, user_email)
    meter.counter("auth.login.attempts", labels={"email": user_email, "status": "failed"})
