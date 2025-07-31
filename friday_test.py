import requests
import json
import time

BASE_URL = "http://localhost:8000"

def log(msg):
    print(f"\n[+] {msg}")

def test_health():
    try:
        res = requests.get(f"{BASE_URL}/health")
        assert res.status_code == 200 and res.json()["status"] == "healthy"
        log("Health check ✅ passed")
    except Exception as e:
        log(f"Health check ❌ failed: {e}")

def test_clear_context():
    try:
        res = requests.delete(f"{BASE_URL}/context/clear")
        assert res.status_code == 200
        log("Context clear ✅ passed")
    except Exception as e:
        log(f"Context clear ❌ failed: {e}")

def test_store_context():
    try:
        payload = {"text": "The capital of Russia is Moscow.", "metadata": {"source": "test_script"}}
        res = requests.post(f"{BASE_URL}/context/store", json=payload)
        assert res.status_code == 200 and "id" in res.json()
        log("Store context ✅ passed")
        return res.json()["id"]
    except Exception as e:
        log(f"Store context ❌ failed: {e}")
        return None

def test_retrieve_context():
    try:
        res = requests.get(f"{BASE_URL}/context/retrieve", params={"query": "Russia"})
        assert res.status_code == 200 and isinstance(res.json(), list)
        if res.json():
            assert "Moscow" in res.json()[0]["text"]
        log("Retrieve context ✅ passed")
    except Exception as e:
        log(f"Retrieve context ❌ failed: {e}")

def test_prompt_pipeline():
    try:
        query = "What is the capital of Russia?"
        res = requests.post(f"{BASE_URL}/process", json={"input": query})
        assert res.status_code == 200
        answer = res.json().get("output", "")
        if "Moscow" in answer:
            log(f"Prompt execution ✅ passed: {answer}")
        else:
            log(f"Prompt execution ⚠️ possibly wrong answer: {answer}")
    except Exception as e:
        log(f"Prompt execution ❌ failed: {e}")

def test_history():
    try:
        res = requests.get(f"{BASE_URL}/context/history")
        assert res.status_code == 200 and isinstance(res.json(), list)
        log("History check ✅ passed")
    except Exception as e:
        log(f"History check ❌ failed: {e}")

if __name__ == "__main__":
    log("🔍 Starting End-to-End FRIDAY Test")
    test_health()
    test_clear_context()
    ctx_id = test_store_context()
    time.sleep(1)
    test_retrieve_context()
    time.sleep(1)
    test_prompt_pipeline()
    time.sleep(1)
    test_history()
    log("✅ Test run complete")
