# Blue/Green Deployment Runbook

## Overview
This runbook provides guidance for operators managing the blue/green deployment with automated observability and Slack alerting.

---

## Alert Types & Response Procedures

### 🔄 Failover Detected

**Alert Example:**
```
Failover Detected
• Previous Pool: blue
• Current Pool: green
• Timestamp: 2025-11-02 02:55:08

Action Required:
1. Check health of blue container
2. Review logs for errors
3. Verify green is handling traffic correctly
```

**What This Means:**
Traffic has automatically switched from one pool (blue/green) to another due to the primary pool becoming unhealthy or unresponsive.

**Immediate Actions:**
1. **Check the failed pool's health:**
   ```bash
   docker compose ps
   docker compose logs <failed-pool>  # e.g., blue or green
   ```

2. **Review Nginx error logs:**
   ```bash
   docker compose logs nginx | grep error
   ```

3. **Verify the new pool is serving traffic correctly:**
   ```bash
   # Check pool serving traffic
   curl -i http://localhost:8080/version | grep X-App-Pool
   
   # Make several requests to confirm stability
   for i in {1..10}; do curl http://localhost:8080/version; done
   ```

4. **Investigate root cause:**
   - Check application logs for crashes or errors
   - Verify resource availability (CPU, memory, disk)
   - Check for external dependency failures (database, APIs)
   - Review recent deployments or configuration changes

**Recovery Steps:**
1. Fix the issue in the failed pool
2. Restart the affected container:
   ```bash
   docker compose restart <pool-name>
   ```
3. Stop chaos mode if it was active:
   ```bash
   curl -X POST http://localhost:8081/chaos/stop  # for blue
   curl -X POST http://localhost:8082/chaos/stop  # for green
   ```
4. Monitor for automatic failback (if configured) or manually toggle pools

---

### ⚠️ High Error Rate

**Alert Example:**
```
High Error Rate Detected
• Error Rate: 8.98% (threshold: 2.0%)
• Errors: 15/167 requests
• Window Size: 200 requests
• Current Pool: blue

Action Required:
1. Check upstream application logs
2. Verify database/external service connectivity
3. Consider manual pool toggle if issues persist
```

**What This Means:**
More than 2% of requests (configurable via `ERROR_RATE_THRESHOLD`) are returning 5xx errors over a sliding window of 200 requests (configurable via `WINDOW_SIZE`).

**Immediate Actions:**
1. **Check application logs for errors:**
   ```bash
   docker compose logs blue green --tail=100
   ```

2. **Verify upstream dependencies:**
   - Database connectivity
   - External API availability
   - Network connectivity
   - Resource constraints (CPU, memory)

3. **Check system resources:**
   ```bash
   docker stats
   ```

4. **Review recent Nginx logs:**
   ```bash
   docker compose exec nginx tail -50 /var/log/nginx/access.log | jq '.'
   ```

**Recovery Steps:**
1. If errors persist on current pool, consider manual toggle:
   ```bash
   # Edit .env file
   ACTIVE_POOL=green  # switch to the other pool
   
   # Reload Nginx configuration
   docker compose restart nginx
   ```

2. If errors are widespread (both pools), investigate:
   - Shared dependencies (database, cache, external APIs)
   - Network issues
   - Configuration problems

3. Monitor error rate after remediation:
   ```bash
   docker compose logs alert_watcher | tail -20
   ```

---

### ℹ️ Watcher Started

**Alert Example:**
```
Watcher Started
Monitoring is now active.
Initial pool: blue
```

**What This Means:**
The alert watcher service has successfully started and is monitoring Nginx logs.

**Action Required:**
None - this is an informational alert confirming the monitoring system is operational.

---

## Manual Operations

### Manual Pool Toggle

To manually switch traffic between blue and green pools:

1. **Edit `.env` file:**
   ```bash
   ACTIVE_POOL=green  # or blue
   ```

2. **Reload Nginx:**
   ```bash
   docker compose restart nginx
   ```

3. **Verify the change:**
   ```bash
   curl -i http://localhost:8080/version | grep X-App-Pool
   ```

---

### Triggering Chaos for Testing

To test failover behavior:

1. **Start chaos mode (simulate failures):**
   ```bash
   # Error mode (returns 500 errors)
   curl -X POST http://localhost:8081/chaos/start?mode=error
   
   # Timeout mode (delays responses)
   curl -X POST http://localhost:8081/chaos/start?mode=timeout
   ```

2. **Make requests through Nginx:**
   ```bash
   for i in {1..20}; do 
     curl http://localhost:8080/version
     sleep 0.5
   done
   ```

3. **Observe failover in logs:**
   ```bash
   docker compose logs -f alert_watcher
   ```

4. **Stop chaos mode:**
   ```bash
   curl -X POST http://localhost:8081/chaos/stop
   curl -X POST http://localhost:8082/chaos/stop
   ```

---

## Maintenance Mode

During planned maintenance or testing, you may want to suppress non-critical alerts.

### Enable Maintenance Mode:
```bash
# Edit .env
MAINTENANCE_MODE=true

# Restart watcher
docker compose restart alert_watcher
```

**What's Suppressed:**
- Failover alerts (info/recovery)
- Non-critical notifications

**What's NOT Suppressed:**
- Critical alerts
- Error rate alerts above threshold

### Disable Maintenance Mode:
```bash
# Edit .env
MAINTENANCE_MODE=false

# Restart watcher
docker compose restart alert_watcher
```

---

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SLACK_WEBHOOK_URL` | Required | Slack incoming webhook URL for alerts |
| `ACTIVE_POOL` | `blue` | Initial active pool (blue or green) |
| `ERROR_RATE_THRESHOLD` | `2` | Error rate percentage threshold for alerts |
| `WINDOW_SIZE` | `200` | Number of requests to track for error rate |
| `ALERT_COOLDOWN_SEC` | `300` | Seconds between duplicate alerts (5 minutes) |
| `MAINTENANCE_MODE` | `false` | Suppress non-critical alerts |

### Adjusting Alert Sensitivity

**To reduce alert noise:**
```bash
# Increase error threshold
ERROR_RATE_THRESHOLD=5

# Increase cooldown period
ALERT_COOLDOWN_SEC=600  # 10 minutes

# Increase window size (more stable)
WINDOW_SIZE=500
```

**To increase alert sensitivity:**
```bash
# Decrease error threshold
ERROR_RATE_THRESHOLD=1

# Decrease cooldown period
ALERT_COOLDOWN_SEC=60  # 1 minute

# Decrease window size (faster detection)
WINDOW_SIZE=50
```

After changing configuration:
```bash
docker compose restart alert_watcher
```

---

## Monitoring & Debugging

### Check Watcher Status
```bash
docker compose logs alert_watcher | tail -50
```

### View Nginx Logs
```bash
# JSON formatted logs
docker compose exec nginx tail -f /var/log/nginx/access.log | jq '.'

# Recent errors
docker compose exec nginx tail -100 /var/log/nginx/access.log | jq 'select(.status >= 500)'
```

### Test Slack Webhook
```bash
curl -X POST $SLACK_WEBHOOK_URL \
  -H 'Content-Type: application/json' \
  -d '{"text":"Test alert from Blue/Green deployment"}'
```

### Check Service Health
```bash
# All services
docker compose ps

# Specific pool
curl http://localhost:8081/healthz  # blue
curl http://localhost:8082/healthz  # green
curl http://localhost:8080/healthz  # nginx
```

### View Container Resource Usage
```bash
docker stats
```

---

## Troubleshooting

### No Alerts Being Sent

**Check:**
1. Slack webhook is configured correctly:
   ```bash
   docker compose exec alert_watcher env | grep SLACK_WEBHOOK_URL
   ```

2. Watcher is processing logs:
   ```bash
   docker compose logs alert_watcher | grep "Processed"
   ```

3. Test webhook manually (see Monitoring section above)

### False Positive Failover Alerts

**Causes:**
- Transient network issues
- Brief container restarts
- Load-based temporary failures

**Solutions:**
- Increase `ALERT_COOLDOWN_SEC` to reduce duplicate alerts
- Increase Nginx `fail_timeout` and `max_fails` for more tolerance
- Review application health checks

### Error Rate Always High

**Causes:**
- Upstream status includes retry attempts (e.g., `500, 200`)
- Actual application errors
- External dependency failures

**Solutions:**
1. Check if errors are real client failures:
   ```bash
   docker compose exec nginx tail -100 /var/log/nginx/access.log | jq 'select(.status >= 500)'
   ```

2. Investigate application logs for root cause
3. Consider adjusting `ERROR_RATE_THRESHOLD` if retry behavior is expected

---

## Emergency Procedures

### Complete Service Outage

1. **Check all containers:**
   ```bash
   docker compose ps
   ```

2. **Restart failed services:**
   ```bash
   docker compose restart
   ```

3. **Check logs for errors:**
   ```bash
   docker compose logs --tail=100
   ```

4. **If issues persist, rebuild:**
   ```bash
   docker compose down
   docker compose up -d --build
   ```

### Both Pools Failing

This indicates a shared dependency issue:

1. **Check external dependencies:**
   - Database connectivity
   - External API availability
   - Network infrastructure

2. **Review Nginx configuration:**
   ```bash
   docker compose exec nginx nginx -t
   ```

3. **Check for resource exhaustion:**
   ```bash
   docker stats
   df -h
   free -m
   ```

### Alert Storm (Too Many Alerts)

1. **Enable maintenance mode immediately:**
   ```bash
   # Quick command
   docker compose exec alert_watcher sh -c 'export MAINTENANCE_MODE=true'
   ```

2. **Identify and fix root cause**

3. **Adjust alert sensitivity (see Configuration section)**

4. **Re-enable alerts:**
   ```bash
   MAINTENANCE_MODE=false
   docker compose restart alert_watcher
   ```

---

## Testing the Setup

Use the provided test script:

```bash
# Run comprehensive failover test
./test-failover.sh
```

This script will:
- Check all services are running
- Verify baseline traffic routing
- Trigger chaos on active pool
- Confirm automatic failover
- Validate Slack alerts were sent
- Display logs and metrics

---

## Best Practices

1. **Regular Testing:** Run chaos drills weekly to ensure failover works
2. **Monitor Trends:** Track error rates and failover frequency over time
3. **Alert Tuning:** Adjust thresholds based on your application's normal behavior
4. **Documentation:** Keep this runbook updated with lessons learned
5. **On-Call Readiness:** Ensure operators have access to Slack and infrastructure

---

## Support & Escalation

### Self-Service
- Review this runbook
- Check container logs
- Test individual components

### Escalation Path
1. On-call engineer (Slack alerts)
2. DevOps team lead
3. Platform engineering team

### Critical Issues
For production-impacting issues:
1. Acknowledge the Slack alert immediately
2. Assess impact (partial or complete outage)
3. Follow emergency procedures above
4. Notify stakeholders via incident channel
5. Document incident for post-mortem

---

## Appendix

### Useful Commands Cheat Sheet

```bash
# View all services
docker compose ps

# Restart specific service
docker compose restart <service>

# View logs
docker compose logs -f <service>

# Execute command in container
docker compose exec <service> <command>

# Check Nginx config
docker compose exec nginx nginx -t

# Make requests
curl -i http://localhost:8080/version

# Trigger chaos
curl -X POST http://localhost:8081/chaos/start?mode=error

# Stop chaos
curl -X POST http://localhost:8081/chaos/stop

# Check which pool is active
curl -i http://localhost:8080/version | grep X-App-Pool

# View recent alerts
docker compose logs alert_watcher | grep "DETECTED"
```

---

**Document Version:** 1.0  
**Last Updated:** 2025-11-02  
**Maintained By:** DevOps Team
