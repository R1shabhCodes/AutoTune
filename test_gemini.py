import urllib.request
import json
import os

def test_model(model_name):
    print(f"\n--- Testing Model: {model_name} ---")
    key = ""
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    if k.strip() == "GEMINI_API_KEY":
                        key = v.strip().strip('"').strip("'")
                        break
                        
    if not key:
        print("Error: No GEMINI_API_KEY found in .env")
        return False
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
    payload = {
        "contents": [{"parts": [{"text": "Hello, answer in one word: YES"}]}],
        "generationConfig": {
            "temperature": 0.5
        }
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            resp = json.loads(res.read().decode("utf-8"))
            text = resp["candidates"][0]["content"]["parts"][0]["text"]
            print(f"Success! Response: {text.strip()}")
            return True
    except Exception as e:
        print(f"Failed with error: {e}")
        if hasattr(e, "read"):
            try:
                error_body = e.read().decode("utf-8")
                print("Error Details:")
                print(error_body)
            except Exception:
                pass
        return False

# Test common models
test_model("gemini-1.5-flash")
test_model("gemini-2.5-flash")
test_model("gemini-2.0-flash")
