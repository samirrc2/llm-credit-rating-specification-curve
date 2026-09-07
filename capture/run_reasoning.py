#!/usr/bin/env python3
"""Reasoning-architecture arm (reviewer R2: 'evaluate modern reasoning architectures / CoT').
Runs the frozen 12-specification grid x 45 credit-health items x 3 seeds on a REASONING model
via OpenRouter (OpenAI-compatible). A reasoning model (e.g. DeepSeek-R1) emits chain-of-thought
natively, so this simultaneously answers 'reasoning pipeline / CoT' and 'a third, open-weight
vendor/architecture'. LOCAL execution only (sandbox has no network/keys).

Key (free or paid): put OPENROUTER_API_KEY in ../../API Keys/keys.env.txt
Model: env MODEL_REASONING (default 'deepseek/deepseek-r1:free' = $0, rate-limited;
       'deepseek/deepseek-r1' ~ a few $ for the full grid).

RUN:
  PILOT_MOCK=1 python3 run_reasoning.py                 # offline dry-run, no key/cost
  MODEL_REASONING=deepseek/deepseek-r1 python3 run_reasoning.py   # real run
Resume-safe; writes capture/reasoning_runs/run_<ts>/ (per-call JSON + panel).
"""
from __future__ import annotations
import os, json, time, re, hashlib, urllib.request, urllib.error, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

CONCURRENCY=int(os.environ.get("CONCURRENCY","10"))   # parallel workers

HERE=Path(__file__).resolve().parent; ROOT=HERE.parent
MOCK=os.environ.get("PILOT_MOCK")=="1"
SEEDS=[11,22,33]
MAX_OUTPUT_TOKENS=int(os.environ.get("MAX_OUTPUT_TOKENS","8192"))   # room for reasoning trace + the rating
MODEL=os.environ.get("MODEL_REASONING","deepseek/deepseek-r1:free")
MAX_SPEND_USD=float(os.environ.get("MAX_SPEND_USD","15"))
TPL=json.load(open(ROOT/"data"/"frozen"/"main"/"paraphrase_templates.json"))
_b=json.load(open(ROOT/"data"/"frozen"/"main"/"battery_90.json"))
ITEMS=[it for it in (_b["items"] if isinstance(_b,dict) else _b) if it.get("benchmark_label") in ("SAFE","WATCH","DISTRESS")]
SPECS=json.load(open(ROOT/"data"/"frozen"/"realarm"/"spec_grid_12.json"))["specs"]
RS=json.load(open(ROOT/"data"/"frozen"/"main"/"rating_scale.json")); IGHY=RS["letter_to_ig_hy"]
FAM="credit_health"

RUNS=HERE/"reasoning_runs"; RUNS.mkdir(exist_ok=True); _A=RUNS/".active_run"
if MOCK: RID="mock"
elif _A.exists() and os.environ.get("RE_NEW_RUN")!="1": RID=_A.read_text().strip()
else: RID=datetime.now().strftime("%Y%m%d_%H%M%S")
RUN=RUNS/("run_mock" if MOCK else f"run_{RID}"); RAW=RUN/"raw"; RAW.mkdir(parents=True,exist_ok=True)
if not MOCK: _A.write_text(RID)

def load_keys():
    f=ROOT.parent/"API Keys"/"keys.env.txt"
    if not f.exists(): return
    for ln in f.read_text().splitlines():
        ln=ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k,v=ln.split("=",1); k,v=k.strip(),v.strip().strip('"').strip("'")
            if v and not os.environ.get(k): os.environ[k]=v
load_keys()
def key():
    k=os.environ.get("OPENROUTER_API_KEY")
    if not k and not MOCK: raise SystemExit("Set OPENROUTER_API_KEY in ../../API Keys/keys.env.txt")
    return k

ORDER=["AAA","AA+","AA","AA-","A+","A","A-","BBB+","BBB","BBB-","BB+","BB","BB-","B+","B","B-","CCC+","CCC","CCC-","CC","C"]
def band(sp):
    if sp not in ORDER: return None
    i=ORDER.index(sp); return "SAFE" if i<=ORDER.index("BBB-") else "WATCH" if i<=ORDER.index("B-") else "DISTRESS"
def render_facts(item,lvl):
    L=TPL["presentation_levels"][lvl]; kv=list(reversed(item["facts_kv"])) if L["order"]=="reversed" else item["facts_kv"][:]
    if L["layout"]=="table" and kv:
        w=max(len(k) for k,_ in kv); return "\n".join(f"| {k.ljust(w)} | {v} |" for k,v in kv)
    return item["facts_text"]
def build_prompt(item,spec):
    fam=TPL["families"][FAM]
    base=TPL["paraphrases"][spec["A4_paraphrase"]].format(role=fam["role"],question=fam["question"],
        labels=", ".join(fam["labels"]),asof="the most recent fiscal year",
        facts_block=render_facts(item,"L1" if spec["A7_presentation"].startswith("L1") else "L0"),
        fewshot_block="",format_block=TPL["format_blocks"][spec["A5_format"]])
    return "Reason step by step, then give your final answer.\n\n"+base   # explicit CoT

def call(model,prompt,seed):
    url="https://openrouter.ai/api/v1/chat/completions"
    hdr={"Content-Type":"application/json","Authorization":f"Bearer {key()}"}
    body={"model":model,"messages":[{"role":"user","content":prompt}],"max_tokens":MAX_OUTPUT_TOKENS,"seed":seed}
    req=urllib.request.Request(url,data=json.dumps(body).encode(),headers=hdr,method="POST")
    with urllib.request.urlopen(req,timeout=240) as r: j=json.loads(r.read().decode())
    msg=j["choices"][0]["message"]; u=j.get("usage",{})
    txt=(msg.get("content") or ""); rsn=(msg.get("reasoning") or "")   # R1 puts CoT in 'reasoning'
    return txt, rsn, u.get("prompt_tokens",0), u.get("completion_tokens",0)
def mock_call(model,prompt,seed):
    h=int(hashlib.sha256(f"{model}|{prompt}|{seed}".encode()).hexdigest(),16)
    return json.dumps({"rating":ORDER[h%len(ORDER)]}),"",len(prompt)//4,600
GRADE=re.compile(r"(?<![A-Za-z0-9])(AAA|AA[+-]?|A[+-]?|BBB[+-]?|BB[+-]?|B[+-]?|CCC[+-]?|CC|C)(?![A-Za-z0-9])")
def parse(txt):
    m=re.search(r'"rating"\s*:\s*"([^"]+)"',txt) or re.search(r'\brating\b[^A-Za-z0-9]{0,6}([A-C]{1,3}[+-]?)',txt,re.I)
    if m:
        g=m.group(1).upper().replace(" ","")
        if g in ORDER: return g
    c=GRADE.findall(txt); return c[-1] if c else None
# rough price for the spend cap ($/1M) — adjust to your model
PIN,POUT=(float(x) for x in os.environ.get("PRICE","0.55,2.19").split(","))

def main():
    TOT=len(ITEMS)*len(SPECS)*len(SEEDS)
    tasks=[(it,sp,seed) for it in ITEMS for sp in SPECS for seed in SEEDS]
    st={"spend":0.0,"done":0,"stop":False}; lock=threading.Lock(); rows=[]
    print(f"REASONING arm — model={MODEL} — {TOT} calls ({len(ITEMS)}x{len(SPECS)}x{len(SEEDS)}) x{CONCURRENCY} workers {'[MOCK]' if MOCK else ''}")
    def work(task):
        it,sp,seed=task
        fp=RAW/f"{sp['spec_id']}_{it['item_id']}_s{seed}.json"
        if fp.exists():
            try:
                d=json.loads(fp.read_text())
                if d.get("ok"):
                    with lock: st["done"]+=1
                    return d
            except: pass
        if st["stop"]: return None
        pr=build_prompt(it,sp)
        try:
            txt,rsn,i,o=(mock_call if MOCK else call)(MODEL,pr,seed)
            c=i/1e6*PIN+o/1e6*POUT
            let=parse(txt) or parse(rsn)          # answer in content, else recover from the reasoning trace
            rec={"spec_id":sp["spec_id"],"item_id":it["item_id"],"benchmark_label":it.get("benchmark_label"),
                "provider":"openrouter","model":MODEL,"tier":"reasoning","seed":seed,
                "presentation":sp["A7_presentation"],"paraphrase":sp["A4_paraphrase"],"format":sp["A5_format"],
                "ok":bool(let),"raw_response":(txt or "")[:4000],"reasoning_tail":(rsn or "")[-1500:],
                "parsed_letter":let,"parsed_band":band(let) if let else None,
                "parsed_ighy":IGHY.get(let) if let else None,"in_tok":i,"out_tok":o,"usd":round(c,6),
                "utc":datetime.now(timezone.utc).isoformat()}
            fp.write_text(json.dumps(rec,indent=1))
            with lock:
                st["spend"]+=c; st["done"]+=1
                if st["spend"]>MAX_SPEND_USD: st["stop"]=True
                if st["done"]%20==0 or st["done"]<=5:
                    print(f"  [{st['done']:4d}/{TOT} {100*st['done']/TOT:5.1f}%] last {sp['spec_id']} {it['item_id']} s{seed}: {str(let or '(empty)'):5}->{rec['parsed_ighy'] or '?'} (${st['spend']:.3f})")
            return rec
        except Exception as e:
            with lock: print(f"  {sp['spec_id']} {it['item_id']} s{seed}: ERROR {e}")
            return None
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        for r in ex.map(work, tasks):
            if r: rows.append(r)
    ok=[r for r in rows if r.get("parsed_ighy")]
    (RUN/"reasoning_panel.json").write_text(json.dumps({"utc":datetime.now(timezone.utc).isoformat(),"model":MODEL,
        "n_calls":len(rows),"n_parsed":len(ok),"ighy_dist":dict(Counter(r["parsed_ighy"] for r in ok)),"rows":rows},indent=1))
    print(f"\n=== DONE === {len(rows)}/{TOT} parsed {len(ok)} spend ${st['spend']:.4f} -> reasoning_panel.json")

if __name__=="__main__": main()
