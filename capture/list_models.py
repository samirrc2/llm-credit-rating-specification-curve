#!/usr/bin/env python3
"""List the models your API keys can actually call (names only; keys never printed).
Run locally:  python3 list_models.py
Keys auto-load from ../../API Keys/keys.env.txt."""
from __future__ import annotations
import os, json, urllib.request, urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

def load_keys():
    f = ROOT.parent / "API Keys" / "keys.env.txt"
    if not f.exists(): return
    for line in f.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); k, v = k.strip(), v.strip().strip('"').strip("'")
            if v and not os.environ.get(k): os.environ[k] = v
load_keys()

def get(url, hdr=None):
    req = urllib.request.Request(url, headers=hdr or {})
    with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read().decode())

# ---- Google: list models supporting generateContent -----------------------------
gkey = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY_1")
print("=== GOOGLE models supporting generateContent ===")
if gkey:
    try:
        j = get(f"https://generativelanguage.googleapis.com/v1beta/models?key={gkey}&pageSize=200")
        for m in j.get("models", []):
            if "generateContent" in m.get("supportedGenerationMethods", []):
                name = m.get("name", "").replace("models/", "")
                if any(t in name for t in ("pro", "flash", "gemini")):
                    print(f"  {name:38} {m.get('displayName','')}")
    except Exception as e:
        print("  ERROR:", e)
else:
    print("  (no Google/Gemini key found)")

# ---- OpenAI: list model IDs -----------------------------------------------------
okey = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY_1")
print("\n=== OPENAI models (gpt-5* only) ===")
if okey:
    try:
        j = get("https://api.openai.com/v1/models", {"Authorization": f"Bearer {okey}"})
        for m in sorted(d["id"] for d in j.get("data", [])):
            if m.startswith("gpt-5"):
                print(f"  {m}")
    except Exception as e:
        print("  ERROR:", e)
else:
    print("  (no OpenAI key found)")
