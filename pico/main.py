import network
import time
import ujson
import urequests
from machine import Pin, UART

SSID = "YOUR_WIFI_SSID"
PASSWORD = "YOUR_WIFI_PASSWORD"
SPRING_URL = "http://192.168.0.208:8585/api/gps/telemetry"

GPS_DEVICE_ID = "PICO2W-NEO7M-RC-01"
EDGE_NODE_ID = "EDGE-RC-01"
LANE_ID = "RC-DEMO-LANE"
PROVIDER = "pico2w-neo7m"

# Pico UART0: GP1(TX), GP0(RX). Connect NEO-7M TXD -> Pico GP0.
gps_uart = UART(0, baudrate=9600, tx=Pin(1), rx=Pin(0))


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("WiFi connecting...")
        wlan.connect(SSID, PASSWORD)
        for _ in range(30):
            if wlan.isconnected():
                break
            print(".")
            time.sleep(1)
    print("WiFi connected:", wlan.ifconfig())
    return wlan


def post_payload(payload):
    print("POST payload:", payload)
    try:
        response = urequests.post(
            SPRING_URL,
            data=ujson.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        print("POST response:", response.status_code, response.text)
        response.close()
    except Exception as exc:
        print("POST failed:", exc)


def base_payload(fix_status, raw_sentence, status_message):
    return {
        "gpsDeviceId": GPS_DEVICE_ID,
        "edgeNodeId": EDGE_NODE_ID,
        "laneId": LANE_ID,
        "provider": PROVIDER,
        "fixStatus": fix_status,
        "statusMessage": status_message,
        "rawSentence": raw_sentence,
        "speedKmh": 0.0,
        "heading": 0.0,
    }


def to_decimal(raw_value, direction):
    if not raw_value:
        return None
    dot = raw_value.find(".")
    degree_len = dot - 2
    degrees = float(raw_value[:degree_len])
    minutes = float(raw_value[degree_len:])
    value = degrees + minutes / 60
    if direction in ("S", "W"):
        value = -value
    return value


def parse_rmc(sentence):
    parts = sentence.split(",")
    if len(parts) < 10 or not sentence.startswith("$GPRMC"):
        return None

    valid_flag = parts[2]
    if valid_flag != "A":
        payload = base_payload("NO_FIX", sentence, "GPS not fixed yet")
        return payload

    latitude = to_decimal(parts[3], parts[4])
    longitude = to_decimal(parts[5], parts[6])
    speed_kmh = float(parts[7] or 0) * 1.852
    heading = float(parts[8] or 0)

    payload = base_payload("FIXED", sentence, "GPS fixed")
    payload.update({
        "latitude": latitude,
        "longitude": longitude,
        "speedKmh": speed_kmh,
        "heading": heading,
    })
    return payload


connect_wifi()
print("Pico 2 W NEO-7M GPS logger started")

last_no_fix_post_ms = 0

while True:
    if gps_uart.any():
        line = gps_uart.readline()
        if not line:
            continue
        try:
            sentence = line.decode("ascii").strip()
        except UnicodeError:
            continue

        if sentence.startswith("$GPRMC"):
            print(sentence)
            payload = parse_rmc(sentence)
            if payload is None:
                continue

            now_ms = time.ticks_ms()
            if payload["fixStatus"] == "NO_FIX":
                print("GPS not fixed yet")
                # Avoid flooding DB while the antenna is still searching.
                if time.ticks_diff(now_ms, last_no_fix_post_ms) < 10000:
                    continue
                last_no_fix_post_ms = now_ms

            post_payload(payload)

    time.sleep(0.1)
