#!/usr/bin/env python3
"""Test script to verify API keys and models work."""
import sys
sys.path.insert(0, '/app')

from app.api_keys import APIKeyManager
from app.database import SessionLocal
from google import genai
from google.genai import types

db = SessionLocal()
mgr = APIKeyManager(db)
keys = mgr.get_active_keys()

print(f"Found {len(keys)} active keys")

for k in keys:
    print(f"\n=== Key: {k.name} ===")
    client = genai.Client(api_key=k.key)
    
    for model in ["gemini-3-flash-preview", "gemini-2.0-flash"]:
        try:
            response = client.models.generate_content(
                model=model,
                contents="Say hi",
                config=types.GenerateContentConfig(max_output_tokens=10),
            )
            print(f"  {model}: OK - {response.text[:30] if response.text else 'empty'}")
        except Exception as e:
            err = str(e)[:150]
            print(f"  {model}: {err}")
