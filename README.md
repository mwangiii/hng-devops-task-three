# Blue/Green Deployment with Observability & Alerts

A production-ready blue/green deployment setup with Nginx reverse proxy, automated failover, real-time monitoring, and Slack alerting.

## 🎯 Features

- **Blue/Green Deployment:** Zero-downtime deployments with automatic failover
- **Health-Based Failover:** Nginx automatically switches to backup pool on failures
- **Real-Time Monitoring:** Python log watcher tracks pool changes and error rates
- **Slack Alerts:** Instant notifications for failovers and error rate thresholds
- **Alert Cooldowns:** Prevents alert spam with configurable rate limiting
- **JSON Logging:** Structured logs with pool, release, status, and latency
- **Maintenance Mode:** Suppress non-critical alerts during planned maintenance

## 📋 Prerequisites

- Docker and Docker Compose
- Slack workspace with incoming webhook (for alerts)
- Ports 8080, 8081, 8082 available

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/mwangiii/blue-green-deployment.git
cd blue-green-deployment
```

### 2. Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env and set your Slack webhook URL
nano .env
```

**Required Configuration:**
```bash
# Your Slack incoming webhook URL
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Optional: Adjust thresholds
ERROR_RATE_THRESHOLD=2       # Alert if error rate exceeds 2%
WINDOW_SIZE=200              # Track last 200 requests
ALERT_COOLDOWN_SEC=300       # 5 minutes between duplicate alerts
```

### 3. Run the Test Script

```bash
# Make script executable
chmod +x test-failover.sh

# Start services and run comprehensive test
./test-failover.sh
```

The script will:
- ✅ Start all services (blue, green, nginx, alert_watcher)
- ✅ Verify baseline traffic routing
- ✅ Trigger chaos on the active pool
- ✅ Confirm automatic failover to backup pool
- ✅ Validate Slack alerts were sent
- ✅ Display logs and metrics

### 4. Check Slack for Alerts

You should receive alerts for:
1. **Watcher Started** - Monitoring initialized
2. **Failover Detected** - Traffic switched pools
3. **High Error Rate** - Error threshold exceeded

## 📂 Project Structure

```
.
├── docker-compose.yml          # Service orchestration
├── .env.example                # Environment variables template
├── nginx/
│   └── nginx.conf.template     # Nginx reverse proxy config
├── watcher/
│   ├── Dockerfile              # Alert watcher container
│   ├── watcher.py              # Log monitoring script
│   └── requirements.txt        # Python dependencies
├── test-failover.sh            # Automated test script
├── runbook.md                  # Operator guide
└── README.md                   # This file
```

## 🧪 Manual Testing

### Check Services

```bash
# View all services
docker compose ps

# Check which pool is active
curl -i http://localhost:8080/version | grep X-App-Pool
```

### Trigger Failover

```bash
# Induce chaos on blue pool (simulate failures)
curl -X POST http://localhost:8081/chaos/start?mode=error

# Make requests - should automatically failover to green
for i in {1..10}; do 
  curl http://localhost:8080/version
  sleep 0.5
done

# Check logs for failover detection
docker compose logs alert_watcher | tail -20

# Stop chaos
curl -X POST http://localhost:8081/chaos/stop
```

### View Logs

```bash
# Watch alert watcher
docker compose logs -f alert_watcher

# View Nginx logs (JSON format)
docker compose exec nginx tail -f /var/log/nginx/access.log

# Pretty-print JSON logs
docker compose exec nginx tail -20 /var/log/nginx/access.log | jq '.'
```

## 📊 Verification Screenshots

### ✅ Slack Alert - Failover Event
![Failover Alert](screenshots/failover-alert.png)

**Expected Content:**
- Previous pool and current pool
- Timestamp
- Action items for operators

### ✅ Slack Alert - High Error Rate
![Error Rate Alert](screenshots/error-rate-alert.png)

**Expected Content:**
- Error rate percentage
- Number of errors vs total requests
- Current pool
- Action items

### ✅ Container Logs - Structured Format
![Nginx Logs](screenshots/nginx-logs.png)

**Expected Fields:**
```json
{
  "time": "2025-11-02T02:55:08+00:00",
  "remote_addr": "172.18.0.1",
  "request": "GET /version HTTP/1.1",
  "status": 200,
  "pool": "blue",
  "release": "blue-1",
  "upstream_addr": "172.18.0.2:3000",
  "upstream_status": "200",
  "request_time": 0.005
}
```

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BLUE_IMAGE` | Required | Docker image for blue pool |
| `GREEN_IMAGE` | Required | Docker image for green pool |
| `ACTIVE_POOL` | `blue` | Initial active pool |
| `RELEASE_ID_BLUE` | `blue-1` | Release identifier for blue |
| `RELEASE_ID_GREEN` | `green-1` | Release identifier for green |
| `PORT` | `3000` | Application port |
| `SLACK_WEBHOOK_URL` | Required | Slack webhook for alerts |
| `ERROR_RATE_THRESHOLD` | `2` | Error rate % to trigger alert |
| `WINDOW_SIZE` | `200` | Requests to track for error rate |
| `ALERT_COOLDOWN_SEC` | `300` | Seconds between duplicate alerts |
| `MAINTENANCE_MODE` | `false` | Suppress non-critical alerts |

### Adjusting Failover Behavior

Edit `nginx/nginx.conf.template`:

```nginx
upstream app_backend {
    server blue:3000 max_fails=1 fail_timeout=3s;  # Adjust these
    server green:3000 backup;
}
```

- `max_fails`: Number of failed requests before marking unhealthy
- `fail_timeout`: How long to wait before retrying failed upstream

## 🛠️ Troubleshooting

### No Alerts Received

1. **Check Slack webhook:**
   ```bash
   docker compose exec alert_watcher env | grep SLACK_WEBHOOK_URL
   ```

2. **Test webhook manually:**
   ```bash
   curl -X POST $SLACK_WEBHOOK_URL \
     -H 'Content-Type: application/json' \
     -d '{"text":"Test alert"}'
   ```

3. **Check watcher logs:**
   ```bash
   docker compose logs alert_watcher
   ```

### Logs Not Being Processed

```bash
# Check if log files exist
docker compose exec alert_watcher ls -lah /var/log/nginx/

# Verify logs are being written
docker compose exec nginx tail -5 /var/log/nginx/access.log

# Restart watcher
docker compose restart alert_watcher
```

### Pool Not Detected

```bash
# Check if app sends X-App-Pool header
curl -v http://localhost:8081/version 2>&1 | grep -i x-app-pool

# View recent log entries
docker compose exec nginx tail -5 /var/log/nginx/access.log | jq '.'
```

See [runbook.md](runbook.md) for detailed troubleshooting and operator procedures.

## 📖 Documentation

- **[runbook.md](runbook.md)** - Comprehensive operator guide with alert response procedures
- **[.env.example](.env.example)** - All available environment variables

## 🧹 Cleanup

```bash
# Stop all services
docker compose down

# Remove volumes (clears logs)
docker compose down -v

# Remove all (including images)
docker compose down -v --rmi all
```

## 🎓 How It Works

### Normal Operation (Blue Active)
```
Client → Nginx:8080 → Blue:3000 (primary)
                    → Green:3000 (backup, idle)
```

### Failure Detected
```
1. Blue returns 500 or times out
2. Nginx marks blue as failed (max_fails=1)
3. Nginx retries request to Green
4. Client receives 200 from Green
5. Alert Watcher detects pool change → Slack alert
```

### Error Rate Monitoring
```
1. Watcher tails Nginx access logs (JSON format)
2. Tracks last 200 requests in sliding window
3. Calculates error rate (5xx responses)
4. Sends alert if > 2% (configurable)
5. Respects 5-minute cooldown between alerts
```

## 🚨 Important Notes

- **Do not modify app images** - This setup uses pre-built images from Docker Hub
- **Logs are in JSON format** - Watcher requires structured logs to function
- **Alert cooldowns prevent spam** - Adjust `ALERT_COOLDOWN_SEC` based on your needs
- **Maintenance mode** - Use during planned work to suppress non-critical alerts

## 📝 Stage 2 & 3 Requirements

### Stage 2 ✅
- Blue/Green deployment with Docker Compose
- Nginx reverse proxy with health-based failover
- Environment variable configuration
- Zero failed client requests during failover

### Stage 3 ✅
- Structured JSON logging with pool/release tracking
- Python log watcher for real-time monitoring
- Slack alerts for failovers and error rates
- Alert cooldowns and maintenance mode
- Comprehensive runbook for operators

## 📞 Support

For issues or questions:
1. Check [runbook.md](runbook.md) for troubleshooting
2. Review container logs: `docker compose logs`
3. Test individual components as described above

## 📜 License

MIT License - See LICENSE file for details

---

**Built with ❤️ for DevOps Stage 3 Challenge**
