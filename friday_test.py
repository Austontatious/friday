import os
import time
import requests

BASE_URL = f"http://localhost:{os.getenv('FRIDAY_API_PORT', '9001')}"


def log(msg):
    print(f"\n[+] {msg}")


def test_healthz():
    try:
        res = requests.get(f"{BASE_URL}/healthz")
        assert res.status_code == 200 and res.json().get("ok") is True
        log("Healthz ✅ passed")
    except Exception as e:
        log(f"Healthz ❌ failed: {e}")


def test_readyz():
    try:
        res = requests.get(f"{BASE_URL}/readyz")
        assert res.status_code == 200 and "ok" in res.json()
        log("Readyz ✅ passed")
    except Exception as e:
        log(f"Readyz ❌ failed: {e}")


def test_chat():
    try:
        res = requests.post(f"{BASE_URL}/api/chat", json={"prompt": "Hello FRIDAY"})
        assert res.status_code == 200
        text = res.json().get("text", "")
        if text:
            log(f"Chat ✅ passed: {text[:120]}")
        else:
            log("Chat ⚠️ empty response")
    except Exception as e:
        log(f"Chat ❌ failed: {e}")


if __name__ == "__main__":
    log("🔍 Starting Phase 0 FRIDAY Test")
    test_healthz()
    test_readyz()
    time.sleep(1)
    test_chat()
    log("✅ Test run complete")
