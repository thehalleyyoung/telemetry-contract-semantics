ERROR static.secret_logging at case_studies/current/public_static_patterns/app.py:13:9-13:104: logging statement appears to include a credential, token, cookie, or other sensitive value
WARNING static.unsafe_payload_preview at case_studies/current/public_static_patterns/app.py:13:9-13:104: logging statement appears to include a raw payload or unsafe preview field
WARNING static.missing_correlation at case_studies/current/public_static_patterns/app.py:13:9-13:104: error log may be missing trace/request correlation fields
WARNING static.unbounded_label at case_studies/current/public_static_patterns/app.py:14:9-14:93: metric/tag code appears to use a high-cardinality or user-controlled label without bucketing
WARNING static.missing_exception_recording at case_studies/current/public_static_patterns/app.py:11:10-11:58: error span does not record the caught exception
WARNING static.missing_error_status at case_studies/current/public_static_patterns/app.py:11:10-11:58: error span does not set OpenTelemetry ERROR status
WARNING static.missing_remediation_field at case_studies/current/public_static_patterns/app.py:11:10-11:58: error span does not attach required 'remediation_hint' evidence
