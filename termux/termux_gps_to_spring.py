import json
import subprocess
import time
import urllib.error
import urllib.request

SPRING_URL = "http://192.168.0.208:8585/api/gps/telemetry"
GPS_DEVICE_ID = "TERMUX-PHONE-GPS-01"
EDGE_NODE_ID = "PHONE-DEMO-EDGE-01"
LANE_ID = "RC-DEMO-LANE"
PROVIDER = "termux-gps"
POST_INTERVAL_SEC = 3


def termux_location():
    result = subprocess.run(
        ["termux-location", "-p", "gps", "-r", "once"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "termux-location failed")
    return json.loads(result.stdout)


def build_payload(location):
    latitude = location.get("latitude")
    longitude = location.get("longitude")
    if latitude is None or longitude is None:
        return {
            "gpsDeviceId": GPS_DEVICE_ID,
            "edgeNodeId": EDGE_NODE_ID,
            "laneId": LANE_ID,
            "provider": PROVIDER,
            "fixStatus": "NO_FIX",
            "statusMessage": "Termux GPS has no fix",
            "rawSentence": json.dumps(location, ensure_ascii=False)[:180],
            "speedKmh": 0.0,
            "heading": 0.0,
        }

    speed_mps = location.get("speed") or 0.0
    return {
        "gpsDeviceId": GPS_DEVICE_ID,
        "edgeNodeId": EDGE_NODE_ID,
        "laneId": LANE_ID,
        "provider": PROVIDER,
        "fixStatus": "FIXED",
        "statusMessage": "Termux GPS fixed",
        "latitude": latitude,
        "longitude": longitude,
        "speedKmh": speed_mps * 3.6,
        "heading": location.get("bearing") or 0.0,
        "altitudeM": location.get("altitude"),
        "accuracyM": location.get("accuracy"),
    }


def post_payload(payload):
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        SPRING_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status, response.read().decode("utf-8")


def main():
    print("Termux GPS -> Spring started")
    print("Spring URL:", SPRING_URL)
    while True:
        try:
            location = termux_location()
            payload = build_payload(location)
        except Exception as exc:
            payload = {
                "gpsDeviceId": GPS_DEVICE_ID,
                "edgeNodeId": EDGE_NODE_ID,
                "laneId": LANE_ID,
                "provider": PROVIDER,
                "fixStatus": "NO_FIX",
                "statusMessage": "Termux GPS read failed: " + str(exc)[:80],
                "rawSentence": str(exc)[:180],
                "speedKmh": 0.0,
                "heading": 0.0,
            }

        print("POST payload:", payload)
        try:
            status, text = post_payload(payload)
            print("POST response:", status, text)
        except urllib.error.URLError as exc:
            print("POST failed:", exc)

        time.sleep(POST_INTERVAL_SEC)


if __name__ == "__main__":
    main()
