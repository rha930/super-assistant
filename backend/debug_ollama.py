#!/usr/bin/env python3
"""Debug script to test Ollama connectivity."""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4")

print("🔍 Debugging Ollama Connection\n")
print(f"OLLAMA_BASE_URL: {OLLAMA_BASE_URL}")
print(f"OLLAMA_MODEL: {OLLAMA_MODEL}")
print()

# Test 1: Basic connectivity
print("1️⃣  Testing basic connectivity...")
try:
    response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
    print(f"   ✅ Connected! Status: {response.status_code}")
    models = response.json().get("models", [])
    print(f"   📦 Available models ({len(models)}):")
    for m in models:
        name = m.get("name", "unknown")
        print(f"      - {name}")
        if name == OLLAMA_MODEL:
            print(f"      ✅ {OLLAMA_MODEL} is available!")
except requests.exceptions.ConnectionError as e:
    print(f"   ❌ Connection failed: {e}")
    print(f"   💡 Make sure Ollama is running and accessible at {OLLAMA_BASE_URL}")
except requests.exceptions.Timeout as e:
    print(f"   ❌ Connection timed out: {e}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Test 2: Try to generate
if OLLAMA_MODEL:
    print(f"2️⃣  Testing generation with {OLLAMA_MODEL}...")
    try:
        payload = {"model": OLLAMA_MODEL, "prompt": "Say hello", "stream": False}
        response = requests.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        response_text = data.get("response", "")[:100]
        print("   ✅ Generation successful!")
        print(f"   Response: {response_text}...")
    except Exception as e:
        print(f"   ❌ Generation failed: {e}")

print()
print("💡 Troubleshooting:")
print("   - If connection fails, check OLLAMA_BASE_URL in .env")
print("   - If model not found, run: ollama pull gemma4")
print("   - If Ollama not running, start it: ollama serve")
