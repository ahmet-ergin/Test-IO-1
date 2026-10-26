#!/usr/bin/env bash
# SIMULATED end-to-end contract test: Java agent + fake adb against a running backend. NOT a real-device test.
set -euo pipefail
API="${1:-http://localhost:8001}"
JAR="$(dirname "$0")/../../target/recorder-agent.jar"
export FAKE_ADB_STATE=/tmp/fake-adb; rm -rf "$FAKE_ADB_STATE"; mkdir -p "$FAKE_ADB_STATE"
TOKEN=$(curl -s -X POST "$API/api/settings/agent-token" | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
printf 'backend.url=%s\nagent.token=%s\nadb.path=%s\nagent.name=SIMULATED-e2e\n' "$API" "$TOKEN" "$(cd "$(dirname "$0")" && pwd)/fake-adb.sh" > /tmp/agent-sim.properties
java -jar "$JAR" /tmp/agent-sim.properties > /tmp/agent-sim.log 2>&1 & AGENT=$!
trap 'kill $AGENT 2>/dev/null || true' EXIT
sleep 4
rec() { # $1 = name; prints session summary
  SID=$(curl -s -X POST "$API/api/sessions" -H 'Content-Type: application/json' -d "{\"deviceSerial\":\"FAKE-0001\",\"name\":\"$1\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
  sleep 11; curl -s -X POST "$API/api/sessions/$SID/stop" > /dev/null; sleep 4
  curl -s "$API/api/sessions/$SID" | python3 -c 'import sys,json;s=json.load(sys.stdin);print("SESSION",s["name"],s["status"],s["environment"],"events=",s["event_count"]);[print("  LIMIT",l) for l in s["limitations"]]'
  curl -s "$API/api/sessions/$SID/events" | python3 -c 'import sys,json
for e in json.load(sys.stdin): print("  EVENT",e["sequence"],e["action"],e["captureSource"],e["confidence"],e.get("coordinates"),(e.get("element") or {}).get("resourceId"),e.get("inputValue"))'
  curl -s "$API/api/sessions/$SID/export" | python3 -c "import sys,json,jsonschema;d=json.load(sys.stdin);jsonschema.validate(d,json.load(open('/app/shared/contracts/recording-session.v1.schema.json')));print('  EXPORT schema valid, environment=',d['environment'])"
  curl -s -X DELETE "$API/api/sessions/$SID" > /dev/null
}
rec "SIMULATED normal"
touch "$FAKE_ADB_STATE/getevent_denied"; rec "SIMULATED getevent denied"; rm "$FAKE_ADB_STATE/getevent_denied"
SID=$(curl -s -X POST "$API/api/sessions" -H 'Content-Type: application/json' -d '{"deviceSerial":"FAKE-0001","name":"SIMULATED disconnect"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
sleep 5; touch "$FAKE_ADB_STATE/disconnected"; sleep 4
curl -s "$API/api/sessions/$SID" | python3 -c 'import sys,json;s=json.load(sys.stdin);print("SESSION disconnect",s["status"],s["error"])'
curl -s -X DELETE "$API/api/sessions/$SID" > /dev/null; rm -f "$FAKE_ADB_STATE/disconnected"
curl -s -X POST "$API/api/settings/agent-token" > /dev/null   # rotate so the test token is not reused
