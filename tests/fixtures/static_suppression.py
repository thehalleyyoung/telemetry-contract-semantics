def login(logger, token, email):
    # telemetry-contracts: suppress static.secret_logging owner=secops expiry=2099-01-01 span=3:5-3:49 sensitivity=responsible-disclosure reason=SEC-1234
    logger.error("auth.failure token=%s", token)
    # wrong code/span: should not suppress pii logging below
    # telemetry-contracts: suppress static.secret_logging owner=secops expiry=2099-01-01 span=6:5-6:49 sensitivity=responsible-disclosure reason=SEC-1234
    logger.error("auth.failure email=%s", email)
