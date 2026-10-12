#!/usr/bin/env python3
"""Reviewer 3, Concern 2 — the two decontamination experiments. SPENDS MONEY.

Pre-registration: analysis/revision2/SPEC_r3_realarm_experiments.md, hashed BEFORE any call
(sha256 in results/SPEC_r3_realarm_experiments.sha256). The spec fixes the samples, conditions,
estimands, tests, bootstrap unit, reference benchmarks and BOTH decision-rule branches in advance,
including the branch that demotes the real-issuer arm.

  A  ratio-pattern issuer identification   31 x 2 providers x (1 open + 3 closed orderings) = 248
  B  within-issuer scale sensitivity       31 x {0.6,1.0,1.7} x 12 specs x 1 seed          = 1116
                                                                                     total  1364

Call layer, pricing, key loading and prompt construction are reused from capture/run_arm.py and
capture/fingerprint_pilot.py so Experiment B's prompts are byte-identical in construction to the
frozen real-issuer arm; a different prompt builder would make the comparison meaningless.

Every call is written as its own immutable JSON under capture/decontam_runs/run_<stamp>/raw/ and is
never rewritten. Resume-safe: re-running continues the same run. freeze_decontam.py then copies the
run into data/frozen/ and hashes it.

  python3 capture/realarm_decontam.py              # live
  DECON_MOCK=1 python3 capture/realarm_decontam.py # offline dry run, no keys, no spend
  DECON_ONLY=A|B                                   # one experiment only
"""
from __future__ import annotations
import hashlib, json, os, random, re, time, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path

PB = Path(__file__).resolve().parents[1]
FROZEN = PB / "data/frozen/main"
REAL = PB / "data/frozen/realarm"
MOCK = os.environ.get("DECON_MOCK") == "1"
ONLY = os.environ.get("DECON_ONLY", "AB").upper()

MODELS = {"openai": "gpt-5.4-nano", "google": "gemini-3.5-flash"}
PRICES = {"gpt-5.4-nano": (0.20, 1.25), "gemini-3.5-flash": (1.50, 9.00)}
MAX_OUTPUT_TOKENS = 1024
MAX_SPEND_USD = 25.0
SCALES = [0.6, 1.0, 1.7]
N_ORDERINGS = 3
SEED = 20261011
WORKERS = int(os.environ.get('DECON_WORKERS', '10'))

RUNS = PB / "capture/decontam_runs"; RUNS.mkdir(exist_ok=True)
_ACTIVE = RUNS / ".active_run"
if MOCK:
    RUN_ID = "mock"
elif _ACTIVE.exists() and os.environ.get("DECON_NEW_RUN") != "1":
    RUN_ID = _ACTIVE.read_text().strip()
else:
    RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
RUN_DIR = RUNS / (f"run_{RUN_ID}")
RAW = RUN_DIR / "raw"; RAW.mkdir(parents=True, exist_ok=True)
if not MOCK:
    _ACTIVE.write_text(RUN_ID)

# ---------------- keys. Values are never printed. ----------------
def load_keys():
    f = PB.parents[0] / "API Keys" / "keys.env.txt"
    if not f.exists():
        return
    for line in f.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); k, v = k.strip(), v.strip().strip('"').strip("'")
            if v and not os.environ.get(k):
                os.environ[k] = v
load_keys()
# the keys file numbers its keys (OPENAI_API_KEY_1..3); the older scripts looked only for the
# unsuffixed name and would have failed here. Accept both, and rotate on rate limits.
KEY_NAMES = {"openai": ["OPENAI_API_KEY", "OPENAI_API_KEY_1", "OPENAI_API_KEY_2", "OPENAI_API_KEY_3"],
             "google": ["GOOGLE_API_KEY", "GEMINI_API_KEY", "GEMINI_API_KEY_1",
                        "GEMINI_API_KEY_2", "GEMINI_API_KEY_3"]}
_KEYS = {p: [os.environ[n] for n in names if os.environ.get(n)] for p, names in KEY_NAMES.items()}
_KI = {p: 0 for p in _KEYS}
def key_for(p):
    ks = _KEYS[p]
    if not ks:
        raise RuntimeError(f"no API key for {p}")
    return ks[_KI[p] % len(ks)]
def rotate(p):
    _KI[p] += 1

# ---------------- call layer (reused) ----------------
def _http(url, payload, hdr, timeout=45):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=hdr, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}") from None

def call_openai(model, prompt, seed):
    hdr = {"Content-Type": "application/json", "Authorization": f"Bearer {key_for('openai')}"}
    base = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    for extra in ({"max_completion_tokens": MAX_OUTPUT_TOKENS, "seed": seed, "reasoning_effort": "low"},
                  {"max_completion_tokens": MAX_OUTPUT_TOKENS, "seed": seed},
                  {"max_completion_tokens": MAX_OUTPUT_TOKENS}):
        try:
            j = _http("https://api.openai.com/v1/chat/completions", dict(base, **extra), hdr)
            txt = j["choices"][0]["message"]["content"] or ""; u = j.get("usage", {})
            return txt, u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
        except RuntimeError as e:
            if "HTTP 400" in str(e):
                continue
            raise
    return "", 0, 0

def call_google(model, prompt, seed):
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
           f"?key={key_for('google')}")
    gen = {"maxOutputTokens": MAX_OUTPUT_TOKENS, "seed": seed, "thinkingConfig": {"thinkingBudget": 0}}
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": gen}
    try:
        j = _http(url, body, {"Content-Type": "application/json"})
    except RuntimeError as e:
        if "HTTP 400" in str(e):
            gen.pop("thinkingConfig", None)
            j = _http(url, body, {"Content-Type": "application/json"})
        else:
            raise
    cand = (j.get("candidates") or [{}])[0]
    txt = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
    um = j.get("usageMetadata", {})
    return txt, um.get("promptTokenCount", 0), um.get("candidatesTokenCount", 0)

def mock_call(model, prompt, seed):
    h = int(hashlib.sha256(f"{model}|{prompt}|{seed}".encode()).hexdigest(), 16)
    if "CANDIDATES" in prompt:
        return (f"ANSWER: UNKNOWN" if h % 5 else "ANSWER: The Toro Company"), len(prompt) // 4, 6
    if "identify the SPECIFIC company" in prompt:
        return ("GUESS: UNKNOWN" if h % 7 else "GUESS: OLN"), len(prompt) // 4, 5
    return ('{"rating": "%s"}' % ["BBB", "BBB-", "BB+", "A-", "BB"][h % 5]), len(prompt) // 4, 8
ROUTER = {"openai": call_openai, "google": call_google}
def price(model, i, o):
    pin, pout = PRICES[model]; return i / 1e6 * pin + o / 1e6 * pout

# ---------------- inputs ----------------
TPL = json.load(open(FROZEN / "paraphrase_templates.json"))
_b = json.load(open(REAL / "battery_real45.json"))
ITEMS = _b["items"] if isinstance(_b, dict) else _b
ITEMS = [it for it in ITEMS if it.get("benchmark_label") in ("SAFE", "WATCH", "DISTRESS")]
SPECS = json.load(open(REAL / "spec_grid_12.json"))["specs"]
RATIOS = {r["item_id"]: r for r in json.load(open(REAL / "ratio_profiles.json"))["profiles"]}
SEALED = {r["item_id"]: r for r in json.load(open(REAL / "sealed_scoring_key.json"))["key"]}
assert len(ITEMS) == 31 and len(SPECS) == 12, (len(ITEMS), len(SPECS))

# ---- Experiment B prompt: identical construction to the frozen arm (run_arm.build_prompt)
FAM = "credit_health"
def render_facts_kv(kv, lvl_name):
    lvl = TPL["presentation_levels"][lvl_name]
    kv = list(reversed(kv)) if lvl["order"] == "reversed" else list(kv)
    if lvl["layout"] == "table" and kv:
        w = max(len(k) for k, _ in kv)
        return "\n".join(f"| {k.ljust(w)} | {v} |" for k, v in kv)
    return ", ".join(f"{k} {v}" for k, v in kv)
def build_prompt(kv, spec):
    fam = TPL["families"][FAM]
    return TPL["paraphrases"][spec["A4_paraphrase"]].format(
        role=fam["role"], question=fam["question"], labels=", ".join(fam["labels"]),
        asof="the most recent fiscal year",
        facts_block=render_facts_kv(kv, "L1" if spec["A7_presentation"].startswith("L1") else "L0"),
        fewshot_block="", format_block=TPL["format_blocks"][spec["A5_format"]])

def scale_kv(kv, f):
    """Multiply every dollar quantity by f. Ratios are therefore invariant by construction."""
    out = []
    for k, v in kv:
        s = str(v).replace(",", "").strip(); mult = 1.0
        if s.endswith("M"):
            s = s[:-1]
        elif s.endswith("B"):
            s, mult = s[:-1], 1000.0
        try:
            out.append([k, f"{float(s) * mult * f:,.0f}M"])
        except ValueError:
            out.append([k, v])
    return out

# ---- Experiment A prompts
def a1_prompt(iid):
    return ("Below are scale-invariant financial RATIOS for the most recent fiscal year of ONE "
            "real, publicly-listed US company. All absolute monetary amounts have been removed; "
            "only ratios and percentages remain. Using only these ratios, identify the SPECIFIC "
            "company you believe they belong to.\n\n"
            f"{RATIOS[iid]['ratios_only_text']}\n\n"
            "Answer with your single best guess as a company name or stock ticker. If you "
            "genuinely cannot identify a specific company, answer exactly: UNKNOWN.\n"
            "Format: 'GUESS: <name or ticker>' on one line.")

ALL_NAMES = [SEALED[it["item_id"]]["entity_name"] for it in ITEMS]
def a2_prompt(iid, ordering):
    names = list(ALL_NAMES)
    random.Random(SEED + ordering).shuffle(names)
    lines = "\n".join(f"  {i+1}. {n}" for i, n in enumerate(names))
    return ("Below are scale-invariant financial RATIOS for the most recent fiscal year of ONE "
            "real, publicly-listed US company. All absolute monetary amounts have been removed.\n\n"
            f"{RATIOS[iid]['ratios_only_text']}\n\n"
            f"CANDIDATES (exactly one is correct):\n{lines}\n\n"
            "Which candidate do these ratios belong to? Answer with the company name exactly as "
            "written above. If you genuinely cannot tell, answer exactly: UNKNOWN.\n"
            "Format: 'ANSWER: <company name or UNKNOWN>' on one line.")

# ---------------- run ----------------
def jobs():
    if "A" in ONLY:
        for it in ITEMS:
            for prov in MODELS:
                yield ("A1", it["item_id"], prov, None, None, 0, a1_prompt(it["item_id"]))
                for o in range(N_ORDERINGS):
                    yield ("A2", it["item_id"], prov, None, None, o, a2_prompt(it["item_id"], o))
    if "B" in ONLY:
        for it in ITEMS:
            for sc in SCALES:
                kv = scale_kv(it["facts_kv"], sc)
                for sp in SPECS:
                    if sp["A1_provider"] not in MODELS:
                        continue
                    yield ("B", it["item_id"], sp["A1_provider"], sp["spec_id"], sc, 0,
                           build_prompt(kv, sp))

def one(job, state):
    """Execute one call. Each call owns its own immutable file, so workers never collide."""
    exp, iid, prov, spec_id, sc, o, prompt = job
    tag = f"{exp}_{iid}_{prov}" + (f"_{spec_id}_s{sc}" if exp == "B" else f"_o{o}")
    fp = RAW / f"{tag}.json"
    if fp.exists():
        try:
            if json.loads(fp.read_text()).get("ok"):
                return "skip", tag, ""
        except Exception:
            pass
    with state["lock"]:
        if state["spend"] > MAX_SPEND_USD:
            return "cap", tag, ""
    model = MODELS[prov]
    for attempt in range(5):
        try:
            txt, i, oo = (mock_call if MOCK else ROUTER[prov])(model, prompt, SEED)
            c = price(model, i, oo)
            with state["lock"]:
                state["spend"] += c
            fp.write_text(json.dumps(
                {"experiment": exp, "item_id": iid, "provider": prov, "model": model,
                 "spec_id": spec_id, "scale": sc, "ordering": o,
                 "ok": bool(txt.strip()), "raw_response": txt,
                 "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                 "in_tok": i, "out_tok": oo, "usd": round(c, 6),
                 "utc": datetime.now(timezone.utc).isoformat()}, indent=1))
            return ("ok" if txt.strip() else "empty"), tag, txt.strip()[:40]
        except RuntimeError as e:
            s_ = str(e)
            if "402" in s_ or "credits are depleted" in s_ or "billing" in s_:
                return "billing", tag, "provider billing exhausted -- not retried"
            if "429" in s_ or "RESOURCE_EXHAUSTED" in s_ or "503" in s_ or "500" in s_:
                rotate(prov); time.sleep(2 + 4 * attempt); continue
            return "error", tag, s_[:80]
        except Exception as e:
            time.sleep(2); last = str(e)[:80]
    return "error", tag, "retries exhausted"


def main():
    from concurrent.futures import ThreadPoolExecutor
    import threading
    J = list(jobs())
    print(f"decontamination run {RUN_ID}  {'[MOCK]' if MOCK else '[LIVE]'}  {len(J)} calls",
          flush=True)
    print(f"  A: {sum(1 for j in J if j[0].startswith('A'))}   "
          f"B: {sum(1 for j in J if j[0]=='B')}   workers: {WORKERS}", flush=True)
    state = {"spend": 0.0, "lock": threading.Lock()}
    tally = {"ok": 0, "empty": 0, "error": 0, "skip": 0, "cap": 0, "billing": 0}
    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for status, tag, info in ex.map(lambda j: one(j, state), J):
            tally[status] += 1; done += 1
            if status in ("error", "billing") or done % 10 == 0:
                print(f"  [{done:4d}/{len(J)} {100*done/len(J):5.1f}%] {tag[:40]:40} "
                      f"{status:5} {info[:40]:40} (${state['spend']:.3f})", flush=True)
    meta = {"run_id": RUN_ID, "mock": MOCK, "planned_calls": len(J),
            "completed": tally["ok"] + tally["skip"], "empty_completions": tally["empty"],
            "errors": tally["error"], "hit_cap": tally["cap"],
            "billing_blocked": tally["billing"], "usd": round(state["spend"], 4),
            "workers": WORKERS,
            "spec": "analysis/revision2/SPEC_r3_realarm_experiments.md",
            "spec_sha256": open(PB / "results/SPEC_r3_realarm_experiments.sha256").read().split()[0],
            "models": MODELS, "scales": SCALES, "orderings": N_ORDERINGS, "seed": SEED,
            "utc": datetime.now(timezone.utc).isoformat()}
    (RUN_DIR / "run_meta.json").write_text(json.dumps(meta, indent=1))
    print(f"\n  ok={tally['ok']} skip={tally['skip']} empty={tally['empty']} "
          f"error={tally['error']} cap={tally['cap']}  spend=${state['spend']:.3f}", flush=True)
    print(f"  -> {RUN_DIR.relative_to(PB)}", flush=True)


if __name__ == "__main__":
    main()
