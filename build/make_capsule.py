#!/usr/bin/env python3
"""Build paper/reproducibility_capsule_ANONYMIZED.zip from the current tree.

  python3 build/make_capsule.py            # rebuild
  python3 build/make_capsule.py --check    # verify the shipped zip is current and clean

The anonymous manuscript's Data Availability section promises this capsule as supplementary
material, so it is part of the submission rather than a convenience copy. The one shipped
before this rebuild was six weeks stale: it carried the superseded aliasing diagnostics, and
it lacked analysis/revision2/ and the SPEC_*.sha256 pre-registration hashes, so it could not
reproduce the decision-curve, held-out-issuer or SIS-baseline analyses that the revision was
built around.

Anonymisation is applied to THREE metadata files only, and nowhere else:

    CITATION.cff   given-names and affiliation
    README.md      the author line
    .zenodo.json   both affiliation fields

data/raw/realarm/ must never be scrubbed. Those files are the fingerprinting probe's raw
responses and legitimately contain real company names -- "NYT (The New York Times Company)",
"NYCB (New York Community Bancorp)" -- which are the evidence for the identification result.
"Robin" and "chawla" also occur there inside "Robinhood" and "Robinson". Scrubbing them would
corrupt the frozen arm and break its root hash.
"""
from __future__ import annotations
import hashlib, re, sys, zipfile
from pathlib import Path

PB = Path(__file__).resolve().parents[1]
OUT = PB / "paper/reproducibility_capsule_ANONYMIZED.zip"

INCLUDE_DIRS = ["analysis", "capture", "config", "data", "docs", "manifest", "results"]
INCLUDE_FILES = ["reproduce.sh", "requirements.txt", "README.md", "LICENSE", "CITATION.cff",
                 ".zenodo.json", ".gitignore", "DATA_AVAILABILITY.md",
                 "PREREGISTRATION.md", "PREREGISTRATION_AMENDMENTS.md",
                 "REPRODUCIBILITY_DOCUMENTATION.tex", "REPRODUCIBILITY_DOCUMENTATION.pdf"]
SKIP_SUFFIX = (".pyc", ".aux", ".log", ".out", ".blg", ".bbl", ".DS_Store")
SKIP_PARTS = ("__pycache__", ".git", ".venv", ".pytest_cache", "node_modules")

WITHHELD = "Affiliation withheld for double-blind review"
SCRUB = {
    "CITATION.cff": [
        (r'given-names:\s*"(?:Samir|Robin)"', 'given-names: "Author"'),
        (r'family-names:\s*"(?:Chincholikar|Chawla)"', 'family-names: "Anonymous"'),
        (r'affiliation:\s*"[^"]*New York[^"]*"', f'affiliation: "{WITHHELD}"'),
        (r'(?m)^\s*orcid:.*$', "  orcid: https://orcid.org/XXXX-XXXX-XXXX-XXXX"),
        (r'(?m)^\s*email:.*$', "  email: anonymous@example.com"),
        (r'Repository:\s*https://github\.com/\S+', "Repository: [withheld for double-blind review]"),
        (r'(?m)^doi:.*$', 'doi: "[DOI withheld]"'),
        (r'value:\s*"10\.5281/zenodo\.\d+"', 'value: "[DOI withheld]"'),
        (r'10\.5281/zenodo\.\d+', "[DOI withheld]"),
    ],
    ".zenodo.json": [
        (r'"affiliation":\s*"[^"]*New York[^"]*"', '"affiliation": "Withheld for double-blind review"'),
        (r'"name":\s*"(?:Chincholikar|Chawla)[^"]*"', '"name": "Anonymous, Author"'),
        (r'"orcid":\s*"[^"]*"', '"orcid": "XXXX-XXXX-XXXX-XXXX"'),
        (r'Corresponding author: [^.]*\.', "Corresponding author: withheld for double-blind review."),
        (r'"identifier":\s*"https://github\.com/[^"]*"', '"identifier": "[repository withheld]"'),
        (r'https://github\.com/\S*?"', '[repository withheld]"'),
    ],
    "LICENSE": [
        (r"Copyright \(c\) (\d{4}).*", r"Copyright (c) \1 Anonymous Authors"),
    ],
    "DATA_AVAILABILITY.md": [
        (r"\[?10\.5281/zenodo\.\d+\]?(\(https://doi\.org/10\.5281/zenodo\.\d+\))?", "[DOI withheld]"),
        (r"https://github\.com/\S+", "[repository withheld]"),
    ],
    "REPRODUCIBILITY_DOCUMENTATION.tex": [
        (r"\\href\{https://doi\.org/10\.5281/zenodo\.\d+\}\{\\code\{10\.5281/zenodo\.\d+\}\}", "[DOI withheld]"),
        (r"\\url\{https://github\.com/\S*?\}", "[repository withheld]"),
        (r"10\.5281/zenodo\.\d+", "[DOI withheld]"),
        (r"https://github\.com/\S+", "[repository withheld]"),
    ],
    "README.md": [
        (r"\*\*Authors:\*\*.*", "**Authors:** Anonymous Author (affiliation withheld) · "
                               "Anonymous Author (affiliation withheld, corresponding author)"),
        (r"(?m)^\*\*ORCID:\*\*.*$", "**ORCID:** withheld for double-blind review"),
        (r"(?m)^\*\*Contact:\*\*.*$", "**Contact:** withheld for double-blind review"),
        (r"(?m)^\*\*Repository:\*\*.*$", "**Repository:** withheld for double-blind review"),
        (r"(?m)^\*\*Zenodo DOI:\*\*.*$", "**Zenodo DOI:** withheld for double-blind review"),
        (r"https://github\.com/\S+", "[repository withheld]"),
        (r"https://doi\.org/\S+", "[DOI withheld]"),
        (r"10\.5281/zenodo\.\d+", "[DOI withheld]"),
    ],
}
# identity strings that must not survive OUTSIDE data/ and capture/ (study content lives there)
IDENTITY = ["Chincholikar", "samir.chincholikar", "robin.chawla", "0009-0007",
            "New York, USA", "github.com/samirrc2", "10.5281/zenodo"]


def members():
    for d in INCLUDE_DIRS:
        root = PB / d
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*")):
            if p.is_file() and not any(s in p.parts for s in SKIP_PARTS) \
               and not p.name.endswith(SKIP_SUFFIX):
                yield p
    for f in INCLUDE_FILES:
        p = PB / f
        if p.is_file():
            yield p


def content(p: Path) -> bytes:
    rel = str(p.relative_to(PB))
    rules = SCRUB.get(rel)
    if not rules:
        return p.read_bytes()
    t = p.read_text(encoding="utf-8", errors="replace")
    for pat, rep in rules:
        t = re.sub(pat, rep, t)
    return t.encode("utf-8")


def anon_repro_pdf(tmp: Path) -> bytes | None:
    """Compile an anonymised companion PDF.

    REPRODUCIBILITY_DOCUMENTATION.pdf carries the repository URL and Zenodo DOI in its text.
    Scrubbing only the .tex and shipping the original .pdf would leave the identifiers in the
    file a reviewer actually opens."""
    import shutil, subprocess, os
    src = PB / "REPRODUCIBILITY_DOCUMENTATION.tex"
    if not src.exists():
        return None
    stem = "REPRODUCIBILITY_DOCUMENTATION"
    (tmp / f"{stem}.tex").write_bytes(content(src))
    env = dict(os.environ)
    env["PATH"] = os.path.expanduser("~/Library/TinyTeX/bin/universal-darwin") + os.pathsep + env["PATH"]
    for _ in range(2):
        subprocess.run(["pdflatex", "-interaction=nonstopmode", f"{stem}.tex"],
                       cwd=tmp, capture_output=True, env=env)
    out = tmp / f"{stem}.pdf"
    return out.read_bytes() if out.exists() else None


def build() -> dict:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    n, leaks = 0, []
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in members():
            rel = str(p.relative_to(PB))
            b = content(p)
            # study content lives under data/ and capture/ and is never scrubbed, so it is
            # also never scanned: "New York" there is an issuer name, not an affiliation
            if not rel.startswith(("data/", "capture/")) and len(b) < 4_000_000:
                try:
                    t = b.decode("utf-8")
                    for s in IDENTITY:
                        if s in t:
                            leaks.append(f"{rel}: {s}")
                except UnicodeDecodeError:
                    pass
            if rel == "REPRODUCIBILITY_DOCUMENTATION.pdf":
                continue          # written below, from the anonymised source
            z.writestr(rel, b)
            n += 1
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            pdf = anon_repro_pdf(Path(td))
        if pdf:
            z.writestr("REPRODUCIBILITY_DOCUMENTATION.pdf", pdf)
            n += 1
        else:
            leaks.append("REPRODUCIBILITY_DOCUMENTATION.pdf: could not compile an anonymised copy")
    return {"files": n, "leaks": leaks,
            "sha256": hashlib.sha256(OUT.read_bytes()).hexdigest(),
            "mb": OUT.stat().st_size / 1e6}


def check() -> int:
    if not OUT.exists():
        print("NOT CHECKABLE: capsule missing"); return 2
    z = zipfile.ZipFile(OUT)
    names = set(z.namelist())
    required = ["analysis/revision2/r3_decision_curve.py", "analysis/revision2/r3_heldout_issuer.py",
                "analysis/revision2/r3_sis_baselines.py", "results/SPEC_r3_decision_curve.sha256",
                "results/SPEC_r2r3_followups.sha256", "reproduce.sh", "README.md"]
    missing = [r for r in required if r not in names]
    leaks = []
    for n in names:
        if n.startswith(("data/", "capture/")) or n.endswith((".pdf", ".zip", ".parquet", ".png")):
            continue
        try:
            t = z.read(n).decode("utf-8")
        except Exception:
            continue
        for s in IDENTITY:
            if s in t:
                leaks.append(f"{n}: {s}")
    # the bundled README must agree with the repository's current one on the results
    stale = []
    try:
        rm = z.read("README.md").decode("utf-8")
        cur = (PB / "README.md").read_text(encoding="utf-8")
        for v in re.findall(r"\*\*0\.\d+\*\*|\*\*\d+\.\d+ pp\*\*", cur):
            if v.strip("*") not in rm:
                stale.append(v.strip("*"))
    except KeyError:
        stale.append("README.md absent")
    print(f"  capsule files {len(names)}   missing required {len(missing)}   "
          f"identity leaks {len(leaks)}   stale README values {len(stale)}")
    for m in missing[:5]: print(f"    MISSING: {m}")
    for l in leaks[:5]:   print(f"    LEAK   : {l}")
    for s in stale[:5]:   print(f"    STALE  : README lacks {s}")
    if missing or leaks or stale:
        print("FAIL: the shipped capsule is not current or not anonymous"); return 1
    print("PASS: capsule is current, complete and carries no author identity"); return 0


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(check())
    r = build()
    print(f"   wrote {OUT.relative_to(PB)}  {r['files']} files  {r['mb']:.1f} MB  "
          f"sha {r['sha256'][:12]}")
    if r["leaks"]:
        print(f"   FAILED: {len(r['leaks'])} identity leak(s)")
        for l in r["leaks"][:8]: print(f"     {l}")
        sys.exit(1)
    print("   identity check: no author name, email, ORCID, city, repo or DOI outside data/")
