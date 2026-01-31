# Payment Service Runbook

## Overview

This runbook describes how to triage and recover the payment service when users report failed payments.

### Steps

1. Check the `payment-service` pods: `kubectl get pods -l app=payment-service -n prod`.
2. Inspect logs: `kubectl logs <pod> -n prod`.
3. If database connection errors present, restart the DB connection pool and redeploy.
4. If stuck queues are found, run the retry worker: `python workers/retry_failed_payments.py`.

### Contacts

- On-call: payments-team@example.com
