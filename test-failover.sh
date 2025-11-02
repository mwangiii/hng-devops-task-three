#!/bin/bash

echo "🧪 Blue/Green Failover Test Script"
echo "===================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Check initial state
echo "📍 Test 1: Checking initial state (should be Blue)..."
response=$(curl -s -i http://localhost:8080/version 2>&1)
if echo "$response" | grep -q "X-App-Pool: blue"; then
    echo -e "${GREEN}✅ PASS: Traffic is on Blue${NC}"
else
    echo -e "${RED}❌ FAIL: Expected Blue, got:${NC}"
    echo "$response" | grep "X-App-Pool"
    exit 1
fi
echo ""

# Test 2: Trigger chaos on Blue
echo "📍 Test 2: Triggering chaos on Blue..."
chaos_response=$(curl -s -X POST http://localhost:8081/chaos/start?mode=error 2>&1)
echo "Chaos triggered: $chaos_response"
sleep 2
echo ""

# Test 3: Check failover to Green
echo "📍 Test 3: Checking failover to Green..."
response=$(curl -s -i http://localhost:8080/version 2>&1)
if echo "$response" | grep -q "X-App-Pool: green"; then
    echo -e "${GREEN}✅ PASS: Traffic failed over to Green${NC}"
else
    echo -e "${YELLOW}⚠️  WARNING: Expected Green, got:${NC}"
    echo "$response" | grep "X-App-Pool"
fi
echo ""

# Test 4: Send multiple requests to trigger error rate alert
echo "📍 Test 4: Sending 30 requests to verify stability on Green..."
green_count=0
error_count=0
for i in {1..30}; do
    response=$(curl -s -i http://localhost:8080/version 2>&1)
    if echo "$response" | grep -q "X-App-Pool: green"; then
        ((green_count++))
    fi
    if echo "$response" | grep -q "HTTP/1.1 200"; then
        # Success
        echo -n "."
    else
        ((error_count++))
        echo -n "E"
    fi
    sleep 0.2
done
echo ""
echo -e "${GREEN}✅ Green responses: $green_count/30${NC}"
if [ $error_count -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Errors encountered: $error_count${NC}"
else
    echo -e "${GREEN}✅ No errors${NC}"
fi
echo ""

# Test 5: Stop chaos
echo "📍 Test 5: Stopping chaos on Blue..."
stop_response=$(curl -s -X POST http://localhost:8081/chaos/stop 2>&1)
echo "Chaos stopped: $stop_response"
echo ""

# Test 6: Wait for recovery
echo "📍 Test 6: Waiting for recovery back to Blue..."
echo "Waiting 8 seconds for fail_timeout to expire..."
sleep 8
response=$(curl -s -i http://localhost:8080/version 2>&1)
if echo "$response" | grep -q "X-App-Pool: blue"; then
    echo -e "${GREEN}✅ PASS: Traffic recovered back to Blue${NC}"
else
    echo -e "${YELLOW}⚠️  Still on Green (may need more time):${NC}"
    echo "$response" | grep "X-App-Pool"
fi
echo ""

# Summary
echo "===================================="
echo "🎉 Test Complete!"
echo ""
echo "Expected Slack Alerts:"
echo "1. 🔄 Failover: Blue → Green"
echo "2. ✅ Recovery: Green → Blue (after chaos stop)"
echo ""
echo "Check your Slack channel for these alerts!"
echo "===================================="