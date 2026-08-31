#!/usr/bin/env python3
"""Flagship model-tier sub-run (reviewer robustness check). LOCAL execution only
(the analysis sandbox cannot reach provider APIs — DNS/network are blocked there).

Purpose
-------
Tests whether the headline elicitation instability *attenuates on flagship models*.
Re-runs the SAME frozen 12-specification grid (spec_grid_12.json) over the SAME 45
credit-health items used by the confirmatory analysis (battery_90.json, SAFE/WATCH/
DISTRESS only), at the SAME 3 main-study seeds [11,22,33], but with the flagship model
of each provider substituted for the nano/flash tier. The nano/flash side of the
comparison is recomputed OFFLINE from the existing corpus (no new calls) so only the
flagship arm costs anything.

Scope: 45 items x 12 specs x 3 seeds = 1,620 calls  (~half the reviewer's 3,240 est.,
because the 12-spec grid is already 6 OpenAI + 6 Google, one flagship covering its 6).

You must set the two flagship model IDs (this script will NOT guess them):
    export MODEL_OPENAI=<openai-flagship-id>      # e.g. the full-size gpt-5.4
    export MODEL_GOOGLE=<google-flagship-id>      # e.g. gemini-3.5-pro
Keys auto-load from ../../API Keys/keys.env.txt (values never printed).

RUN
---
  # 1) offline dry-run — proves 1,620 calls, grid + battery + prompts, NO keys/spend:
  PILOT_MOCK=1 MODEL_OPENAI=x MODEL_GOOGLE=y python3 run_flagship.py

  # 2) real run (on your Mac, where keys + network live):
  MODEL_OPENAI=<id> MODEL_GOOGLE=<id> python3 run_flagship.py

  # options: FL_NEW_RUN=1 forces a fresh run folder; MAX_SPEND_USD=40 raises the cap;
  #          PRICE_OPENAI="in,out" PRICE_GOOGLE="in,out" set $/1M tokens for the cap.
Resume-safe: re-running continues an interrupted run (never clobbers completed cells).
"""
from __future__ import annotations
import os, json, time, re, hashlib, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                                   # Paper 3/
MOCK = os.environ.get("PILOT_MOCK") == "1"
SEEDS = [11, 22, 33]                                  # main-study seeds (grid_definition.json)
MAX_OUTPUT_TOKENS = int(os.environ.get("MAX_OUTPUT_TOKENS", "4096"))  # higher default: Pro/reasoning models spend tokens thinking before the rating
MAX_SPEND_USD = float(os.environ.get("MAX_SPEND_USD", "40"))

# ---- flagship model IDs (required) ----------------------------------------------
FLAGSHIP = {"openai": os.environ.get("MODEL_OPENAI", "").strip(),
            "google": os.environ.get("MODEL_GOOGLE", "").strip()}
if not MOCK and (not FLAGSHIP["openai"] or not FLAGSHIP["google"]):
    raise SystemExit("Set MODEL_OPENAI and MODEL_GOOGLE to the two flagship model IDs before running.")

# ---- prices ($/1M tokens) for the spend cap; override via PRICE_OPENAI/PRICE_GOOGLE
def _price_env(p, default):
    v = os.environ.get("PRICE_" + p.upper())
    if v:
        i, o = v.split(","); return (float(i), float(o))
    return default
PRICES = {FLAGSHIP["openai"]: _price_env("openai", (15.0, 60.0)),   # conservative defaults
          FLAGSHIP["google"]: _price_env("google", (5.0, 30.0))}    # (only used for the cap)

# ---- frozen inputs (current repo paths) -----------------------------------------
TPL = json.load(open(ROOT / "data" / "frozen" / "main" / "paraphrase_templates.json"))
_b = json.load(open(ROOT / "data" / "frozen" / "main" / "battery_90.json"))
ITEMS = _b["items"] if isinstance(_b, dict) else _b
ITEMS = [it for it in ITEMS if it.get("benchmark_label") in ("SAFE", "WATCH", "DISTRESS")]  # 45 credit items
SPECS = json.load(open(ROOT / "data" / "frozen" / "realarm" / "spec_grid_12.json"))["specs"]
_rs = json.load(open(ROOT / "data" / "frozen" / "main" / "rating_scale.json"))
IGHY = _rs["letter_to_ig_hy"]
FAM = "credit_health"

# ---- run folder (resume-safe) ---------------------------------------------------
RUNS = HERE / "flagship_runs"; RUNS.mkdir(exist_ok=True)
_ACTIVE = RUNS / ".active_run"
if MOCK: RUN_ID = "mock"
elif _ACTIVE.exists() and os.environ.get("FL_NEW_RUN") != "1": RUN_ID = _ACTIVE.read_text().strip()
else: RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
RUN_DIR = RUNS / ("run_mock" if MOCK else f"run_{RUN_ID}"); RAW = RUN_DIR / "raw"; RAW.mkdir(parents=True, exist_ok=True)
if not MOCK: _ACTIVE.write_text(RUN_ID)

# ---- keys (values never printed) ------------------------------------------------
def load_keys():
    f = ROOT.parent / "API Keys" / "keys.env.txt"
    if not f.exists(): return
    for line in f.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); k, v = k.strip(), v.strip().strip('"').strip("'")
            if v and not os.environ.get(k): os.environ[k] = v
load_keys()
def _collect(names):
    out = []
    for n in names:
        v = os.environ.get(n)
        if v and v not in out: out.append(v)
    return out
GKEYS = _collect(["GOOGLE_API_KEY", "GEMINI_API_KEY", "GEMINI_API_KEY_1", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3"])
OKEYS = _collect(["OPENAI_API_KEY", "OPENAI_API_KEY_1", "OPENAI_API_KEY_2", "OPENAI_API_KEY_3"])
_IDX = {"google": 0, "openai": 0}
def _keys(p): return GKEYS if p == "google" else OKEYS
def key_for(p):
    ks = _keys(p)
    if not ks: raise RuntimeError(f"no API key for {p}")
    return ks[_IDX[p] % len(ks)]
def rotate(p):
    """Advance to the next key for provider p; True if another key is available."""
    _IDX[p] += 1
    if _IDX[p] < len(_keys(p)):
        print(f"    -> rotating {p} to key #{_IDX[p]+1}/{len(_keys(p))} (quota/limit on previous)")
        return True
    return False
if not MOCK:
    print(f"  keys loaded: openai={len(OKEYS)}  google={len(GKEYS)}")

# ---- prompt build (identical to run_arm.py) -------------------------------------
def render_facts(item, lvl_name):
    lvl = TPL["presentation_levels"][lvl_name]
    kv = list(reversed(item["facts_kv"])) if lvl["order"] == "reversed" else item["facts_kv"][:]
    if lvl["layout"] == "table" and kv:
        w = max(len(k) for k, _ in kv); return "\n".join(f"| {k.ljust(w)} | {v} |" for k, v in kv)
    return item["facts_text"]
def build_prompt(item, spec):
    fam = TPL["families"][FAM]
    return TPL["paraphrases"][spec["A4_paraphrase"]].format(
        role=fam["role"], question=fam["question"], labels=", ".join(fam["labels"]),
        asof="the most recent fiscal year",
        facts_block=render_facts(item, "L1" if spec["A7_presentation"].startswith("L1") else "L0"),
        fewshot_block="", format_block=TPL["format_blocks"][spec["A5_format"]])

ORDER = ["AAA","AA+","AA","AA-","A+","A","A-","BBB+","BBB","BBB-","BB+","BB","BB-","B+","B","B-","CCC+","CCC","CCC-","CC","C"]
def rating_to_band(sp):
    if sp not in ORDER: return None
    i = ORDER.index(sp); return "SAFE" if i <= ORDER.index("BBB-") else "WATCH" if i <= ORDER.index("B-") else "DISTRESS"

# ---- provider routers (identical to run_arm.py) ---------------------------------
def _http(url, payload, hdr, timeout=90):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=hdr, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8','replace')[:200]}") from None
def call_openai(model, prompt, seed):
    base = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    while True:
        hdr = {"Content-Type": "application/json", "Authorization": f"Bearer {key_for('openai')}"}
        try:
            for extra in ({"max_completion_tokens": MAX_OUTPUT_TOKENS, "seed": seed, "reasoning_effort": "low"},
                          {"max_completion_tokens": MAX_OUTPUT_TOKENS, "seed": seed},
                          {"max_completion_tokens": MAX_OUTPUT_TOKENS}):
                try:
                    j = _http("https://api.openai.com/v1/chat/completions", dict(base, **extra), hdr)
                    txt = j["choices"][0]["message"]["content"] or ""; u = j.get("usage", {})
                    return txt, u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
                except RuntimeError as e:
                    if "HTTP 400" in str(e): continue
                    raise
            return "", 0, 0
        except RuntimeError as e:
            if ("HTTP 429" in str(e) or "HTTP 401" in str(e)) and rotate("openai"): continue
            raise
def call_google(model, prompt, seed):
    """Reasoning-safe: cap thinking cheaply first; only escalate output tokens if a
    cell still returns empty (reasoning models truncate the rating when they overthink)."""
    def once(maxtok, tcfg):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key_for('google')}"
        gen = {"maxOutputTokens": maxtok, "seed": seed}
        if tcfg is not None: gen["thinkingConfig"] = tcfg
        body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": gen}
        try:
            j = _http(url, body, {"Content-Type": "application/json"})
        except RuntimeError as e:
            if "HTTP 400" in str(e) and tcfg is not None:            # budget not accepted -> drop the cap
                return once(maxtok, None)
            if ("HTTP 429" in str(e) or "HTTP 403" in str(e)) and rotate("google"):  # quota depleted -> next key
                return once(maxtok, tcfg)
            raise
        cand = (j.get("candidates") or [{}])[0]
        txt = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
        um = j.get("usageMetadata", {})
        return txt, um.get("promptTokenCount", 0), um.get("candidatesTokenCount", 0), cand.get("finishReason", "")
    # 1) cheap: small thinking budget at the base ceiling; 2)/3) escalate tokens if still empty
    for maxtok, tcfg in [(MAX_OUTPUT_TOKENS, {"thinkingBudget": 128}),
                         (MAX_OUTPUT_TOKENS * 4, None),
                         (min(MAX_OUTPUT_TOKENS * 8, 65536), None)]:
        txt, i, o, fr = once(maxtok, tcfg)
        if txt.strip(): return txt, i, o
    return txt, i, o
def mock_call(model, prompt, seed):
    h = int(hashlib.sha256(f"{model}|{prompt}|{seed}".encode()).hexdigest(), 16)
    return json.dumps({"rating": ORDER[h % len(ORDER)]}), len(prompt) // 4, 8
ROUTER = {"openai": call_openai, "google": call_google}

GRADE = re.compile(r"(?<![A-Za-z0-9])(AAA|AA[+-]?|A[+-]?|BBB[+-]?|BB[+-]?|B[+-]?|CCC[+-]?|CC|C)(?![A-Za-z0-9])")
def parse_letter(txt):
    m = re.search(r'"rating"\s*:\s*"([^"]+)"', txt) or re.search(r'\brating\b[^A-Za-z0-9]{0,6}([A-C]{1,3}[+-]?)', txt, re.I)
    if m:
        g = m.group(1).upper().replace(" ", "")
        if g in ORDER: return g
    cands = GRADE.findall(txt)
    return cands[-1] if cands else None
def price(model, i, o): pin, pout = PRICES.get(model, (0.0, 0.0)); return i / 1e6 * pin + o / 1e6 * pout

def main():
    TOTAL = len(ITEMS) * len(SPECS) * len(SEEDS); spend = 0.0; done = 0; empt = 0; rows = []
    print(f"FLAGSHIP tier sub-run — {TOTAL} calls ({len(ITEMS)} items x {len(SPECS)} specs x {len(SEEDS)} seeds) {'[MOCK]' if MOCK else ''}")
    print(f"  models: openai={FLAGSHIP['openai'] or '(mock)'}  google={FLAGSHIP['google'] or '(mock)'}  cap=${MAX_SPEND_USD:.0f}")
    for it in ITEMS:
        for sp in SPECS:
            prov = sp["A1_provider"]; model = FLAGSHIP[prov] or sp["model"]
            for seed in SEEDS:
                fp = RAW / f"{sp['spec_id']}_{it['item_id']}_s{seed}.json"
                if fp.exists():
                    try:
                        d = json.loads(fp.read_text())
                        if d.get("ok"): rows.append(d); done += 1; continue
                    except Exception: pass
                if spend > MAX_SPEND_USD: print(f"!! cap ${MAX_SPEND_USD} hit; STOP"); break
                prompt = build_prompt(it, sp)
                try:
                    txt, i, o = (mock_call if MOCK else ROUTER[prov])(model, prompt, seed)
                    c = price(model, i, o); spend += c
                    letter = parse_letter(txt); band = rating_to_band(letter) if letter else None
                    ighy = IGHY.get(letter) if letter else None
                    rec = {"spec_id": sp["spec_id"], "item_id": it["item_id"], "benchmark_label": it.get("benchmark_label"),
                           "provider": prov, "model": model, "tier": "flagship", "seed": seed,
                           "presentation": sp["A7_presentation"], "paraphrase": sp["A4_paraphrase"], "format": sp["A5_format"],
                           "ok": bool(txt.strip()), "raw_response": txt, "parsed_letter": letter,
                           "parsed_band": band, "parsed_ighy": ighy,
                           "in_tok": i, "out_tok": o, "usd": round(c, 6), "utc": datetime.now(timezone.utc).isoformat()}
                    fp.write_text(json.dumps(rec, indent=1)); rows.append(rec); done += 1
                    if not txt.strip(): empt += 1
                    print(f"  [{done:4d}/{TOTAL} {100*done/TOTAL:5.1f}%] {sp['spec_id']} {it['item_id']} {prov:6} s{seed}: "
                          f"{str(letter or '(empty)'):5}->{str(ighy or '?'):3} (${spend:.3f})")
                except Exception as e:
                    print(f"  {sp['spec_id']} {it['item_id']} {prov} s{seed}: ERROR {e}"); time.sleep(2)
    ok = [r for r in rows if r.get("parsed_ighy")]
    panel = {"utc": datetime.now(timezone.utc).isoformat(), "run_id": RUN_ID, "tier": "flagship",
             "models": FLAGSHIP, "seeds": SEEDS, "n_calls": len(rows), "n_parsed": len(ok),
             "empty": sum(1 for r in rows if not r.get("ok")),
             "ighy_dist": dict(Counter(r["parsed_ighy"] for r in ok)),
             "band_dist": dict(Counter(r["parsed_band"] for r in rows if r.get("parsed_band"))),
             "by_provider_empty": dict(Counter(r["provider"] for r in rows if not r.get("ok"))),
             "rows": rows}
    (RUN_DIR / "flagship_panel.json").write_text(json.dumps(panel, indent=1))
    print(f"\n=== FLAGSHIP DONE ===\nrun: {RUN_DIR.relative_to(HERE)}")
    print(f"calls {len(rows)}/{TOTAL} | parsed {len(ok)} | empty {panel['empty']} {panel['by_provider_empty']}")
    print(f"IG/HY distribution: {panel['ighy_dist']}")
    print(f"spend ${spend:.4f} -> flagship_panel.json written; hand this run folder back for downstream integration.")

if __name__ == "__main__": main()
