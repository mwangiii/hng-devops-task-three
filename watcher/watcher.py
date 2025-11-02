#!/usr/bin/env python3
import json
import os
import sys
import time
import requests
import subprocess
from collections import deque
from datetime import datetime

class LogWatcher:
    def __init__(self):
        self.slack_webhook = os.getenv('SLACK_WEBHOOK_URL')
        self.active_pool = os.getenv('ACTIVE_POOL', 'blue')
        self.error_rate_threshold = float(os.getenv('ERROR_RATE_THRESHOLD', '2'))
        self.window_size = int(os.getenv('WINDOW_SIZE', '200'))
        self.alert_cooldown = int(os.getenv('ALERT_COOLDOWN_SEC', '300'))
        self.maintenance_mode = os.getenv('MAINTENANCE_MODE', 'false').lower() == 'true'
        
        self.last_pool = self.active_pool
        self.request_window = deque(maxlen=self.window_size)
        self.last_failover_alert = 0
        self.last_error_rate_alert = 0
        self.log_count = 0
        
        print(f"🚀 Alert Watcher initialized")
        print(f"   - Active Pool: {self.active_pool}")
        print(f"   - Error Rate Threshold: {self.error_rate_threshold}%")
        print(f"   - Window Size: {self.window_size}")
        print(f"   - Alert Cooldown: {self.alert_cooldown}s")
        print(f"   - Maintenance Mode: {self.maintenance_mode}")
        print(f"   - Slack Webhook: {'✅ Configured' if self.slack_webhook else '❌ NOT CONFIGURED'}")
        
    def send_slack_alert(self, message, alert_type="info"):
        """Send alert to Slack"""
        print(f"\n🔔 Attempting to send {alert_type} alert...")
        
        if not self.slack_webhook:
            print("❌ No Slack webhook configured, skipping alert")
            return False
            
        if self.maintenance_mode and alert_type != "critical":
            print(f"🔇 Maintenance mode: suppressing {alert_type} alert")
            return False
        
        emoji_map = {
            "failover": "🔄",
            "error_rate": "⚠️",
            "recovery": "✅",
            "critical": "🚨",
            "info": "ℹ️"
        }
        
        emoji = emoji_map.get(alert_type, "ℹ️")
        
        payload = {
            "text": f"{emoji} *Blue/Green Alert*",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{emoji} Blue/Green Alert",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Timestamp:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                        }
                    ]
                }
            ]
        }
        
        print(f"📤 Sending to Slack...")
        try:
            response = requests.post(
                self.slack_webhook,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"✅ Slack alert sent successfully!")
                return True
            else:
                print(f"❌ Slack returned status {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error sending Slack alert: {e}")
            return False
    
    def detect_pool_from_upstream(self, upstream_addr):
        """Detect pool from upstream address - improved version"""
        if not upstream_addr:
            return None

        # upstream_addr can be comma-separated if multiple upstreams tried
        # e.g., "172.18.0.3:3000, 172.18.0.2:3000"
        # We want the LAST one (the one that succeeded)
        addr_lower = str(upstream_addr).lower()

        # Split by comma and take the last non-empty address (successful one)
        addrs = [a.strip() for a in addr_lower.split(',') if a.strip()]
        last_addr = addrs[-1] if addrs else addr_lower

        # Check for service names
        if 'blue' in last_addr:
            return 'blue'
        elif 'green' in last_addr:
            return 'green'

        # Try to detect by port (common mapping)
        # Blue is on 8081, Green is on 8082
        if ':8081' in last_addr or '8081' in last_addr:
            return 'blue'
        elif ':8082' in last_addr or '8082' in last_addr:
            return 'green'

        # Optional: match against env-configured IP lists
        # Set BLUE_IPS / GREEN_IPS env vars to CSV of known IPs if available
        blue_ips = os.getenv('BLUE_IPS', '')
        green_ips = os.getenv('GREEN_IPS', '')
        if blue_ips:
            for ip in [x.strip() for x in blue_ips.split(',') if x.strip()]:
                if ip in last_addr:
                    return 'blue'
        if green_ips:
            for ip in [x.strip() for x in green_ips.split(',') if x.strip()]:
                if ip in last_addr:
                    return 'green'

        # Couldn't determine
        print(f"⚠️  Could not detect pool from upstream_addr: {upstream_addr}")
        return None
    
    def check_failover(self, pool):
        """Detect pool failover"""
        if not pool:
            return False
            
        if pool == self.last_pool:
            return False
            
        current_time = time.time()
        time_since_last = current_time - self.last_failover_alert
        
        # Check cooldown
        if time_since_last < self.alert_cooldown:
            print(f"⏳ Failover detected ({self.last_pool} → {pool}) but in cooldown ({time_since_last:.0f}s / {self.alert_cooldown}s)")
            return False
        
        # Failover detected!
        old_pool = self.last_pool
        self.last_pool = pool
        
        print(f"\n🔄 *** FAILOVER DETECTED *** {old_pool} → {pool}\n")
        
        message = (
            f"*Failover Detected*\n\n"
            f"• Previous Pool: `{old_pool}`\n"
            f"• Current Pool: `{pool}`\n"
            f"• Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"*Action Required:*\n"
            f"1. Check health of `{old_pool}` container\n"
            f"2. Review logs for errors\n"
            f"3. Verify `{pool}` is handling traffic correctly"
        )
        
        self.send_slack_alert(message, "failover")
        self.last_failover_alert = current_time
        return True
    
    def check_error_rate(self):
        """Check if error rate exceeds threshold"""
        if len(self.request_window) < 20:
            return False
        
        error_count = sum(1 for is_error in self.request_window if is_error)
        total_count = len(self.request_window)
        error_rate = (error_count / total_count) * 100
        
        if error_rate <= self.error_rate_threshold:
            return False
        
        current_time = time.time()
        time_since_last = current_time - self.last_error_rate_alert
        
        # Check cooldown
        if time_since_last < self.alert_cooldown:
            return False
        
        print(f"\n⚠️  *** HIGH ERROR RATE *** {error_rate:.2f}% (threshold: {self.error_rate_threshold}%)\n")
        
        message = (
            f"*High Error Rate Detected*\n\n"
            f"• Error Rate: `{error_rate:.2f}%` (threshold: {self.error_rate_threshold}%)\n"
            f"• Errors: {error_count}/{total_count} requests\n"
            f"• Window Size: {self.window_size} requests\n"
            f"• Current Pool: `{self.last_pool}`\n\n"
            f"*Action Required:*\n"
            f"1. Check upstream application logs\n"
            f"2. Verify database/external service connectivity\n"
            f"3. Consider manual pool toggle if issues persist"
        )
        
        self.send_slack_alert(message, "error_rate")
        self.last_error_rate_alert = current_time
        return True
    
    def parse_log_line(self, line):
        """Parse JSON log line"""
        try:
            log_entry = json.loads(line.strip())
            return log_entry
        except json.JSONDecodeError:
            return None
    
    def process_log_entry(self, log_entry):
        """Process a single log entry"""
        if not log_entry:
            return
        
        self.log_count += 1
        
        # Get pool from log or detect from upstream address
        pool = log_entry.get('pool')
        if not pool or pool == '-' or pool == '':
            upstream_addr = log_entry.get('upstream_addr', '')
            pool = self.detect_pool_from_upstream(upstream_addr)
        
        status = log_entry.get('status')
        upstream_status = log_entry.get('upstream_status')
        
        # Debug output every 10 requests
        if self.log_count % 10 == 0:
            print(f"📊 Processed {self.log_count} requests | Pool: {pool or 'unknown'} | Status: {status}")
        
        # Track pool changes
        if pool:
            self.check_failover(pool)
        
        # Track error rate
        is_error = False
        if status and int(status) >= 500:
            is_error = True
        elif upstream_status and str(upstream_status).startswith('5'):
            is_error = True
        
        if is_error:
            print(f"❌ Error detected: status={status}, upstream_status={upstream_status}")
        
        self.request_window.append(is_error)
        
        # Check error rate when we have enough data
        if len(self.request_window) >= 20:
            self.check_error_rate()
    
    def tail_logs_subprocess(self, log_file):
        """Tail nginx logs using tail -f subprocess"""
        print(f"📋 Starting to tail {log_file}")
        
        # Wait for log file to exist
        while not os.path.exists(log_file):
            print(f"⏳ Waiting for log file: {log_file}")
            time.sleep(2)
        
        print(f"✅ Log file found, starting to monitor...\n")
        
        # Use tail -F to follow file even if it rotates
        process = subprocess.Popen(
            ['tail', '-F', '-n', '0', log_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
        
        print(f"🎯 Monitoring active. Waiting for requests...\n")
        
        try:
            for line in iter(process.stdout.readline, ''):
                if line:
                    log_entry = self.parse_log_line(line)
                    if log_entry:
                        self.process_log_entry(log_entry)
        except KeyboardInterrupt:
            process.terminate()
            raise

def main():
    log_file = '/var/log/nginx/access.log'
    
    watcher = LogWatcher()
    
    # Send startup notification
    print("\n🧪 Testing Slack webhook...\n")
    test_message = f"*Watcher Started*\n\nMonitoring is now active.\nInitial pool: `{watcher.active_pool}`"
    watcher.send_slack_alert(test_message, "info")
    print("")
    
    try:
        watcher.tail_logs_subprocess(log_file)
    except KeyboardInterrupt:
        print("\n👋 Shutting down watcher...")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()