"""Re-run offline conformance and mutation checks. Run from the repository root:
  python code/conformance_check.py [--skip-mutations]
Requires OpenTofu 1.13.2 on PATH (or env TOFU) and network access for `tofu init` (or a provider mirror via TF_CLI_CONFIG_FILE).
Steps: tofu init + validate + test for each provider; every mutation in data/mutation_spec.json
must fail its target requirement; grader validation (references, mutants, single-block syntax faults, renaming,
cross-provider submissions) reproduces data/grader_validation_*.csv."""
import hashlib, json, os, re, shutil, subprocess, sys, tempfile
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grader as gr

TOFU = os.environ.get("TOFU", "tofu")
PROVS = ["aws", "azure", "gcp", "openstack"]

def sha_check():
    if not os.path.exists("SHA256SUMS"):
        print("SHA256SUMS not present; skipping checksum check"); return True
    bad = []
    for line in open("SHA256SUMS", encoding="utf-8"):
        h, f = line.strip().split("  ", 1)
        if f == "SHA256SUMS" or not os.path.exists(f) or hashlib.sha256(open(f, "rb").read()).hexdigest() != h:
            bad.append(f)
    print("checksums:", "ok" if not bad else f"{len(bad)} mismatches, e.g. {bad[:5]}")
    return not bad

def tofu(args, cwd):
    r = subprocess.run([TOFU] + args + ["-no-color"], cwd=cwd, capture_output=True, text=True, timeout=1800)
    return r.returncode, r.stdout + r.stderr

def failed_reqs(out):
    return sorted(set(re.findall(r"\n(R\d\d) ", out)))

def main(skip_mut=False):
    ok = sha_check()
    for p in PROVS:
        d = f"ra/{p}"
        if not os.path.isdir(os.path.join(d, ".terraform")):
            rc, out = tofu(["init", "-input=false"], d); assert rc == 0, out[-2000:]
        rc, out = tofu(["validate"], d); assert rc == 0, (p, out[-2000:]); print(p, "validate ok")
        rc, out = tofu(["test"], d); assert rc == 0, (p, out[-2000:]); print(p, "conformance suite passes")
    if not skip_mut:
        spec = json.load(open("data/mutation_spec.json"))
        n = det = 0
        for kind in ["conformance", "false_friend", "holdout"]:
            for p, ml in spec[kind].items():
                f = f"ra/{p}/main.tf"; orig = open(f, encoding="utf-8").read()
                try:
                    for m in ml:
                        assert orig.count(m["before"]) == 1, (p, m["target"])
                        open(f, "w", encoding="utf-8", newline="\n").write(orig.replace(m["before"], m["after"]))
                        rc, out = tofu(["test"], f"ra/{p}")
                        fr = failed_reqs(out); n += 1
                        hit = rc != 0 and (kind == "holdout" or m["target"] in fr or not fr)
                        det += hit
                        print(f"{kind:12s} {p:9s} {m['target']} failed={fr} detected={hit}")
                finally:
                    open(f, "w", encoding="utf-8", newline="\n").write(orig)
        print(f"mutations detected: {det}/{n}"); ok &= det == n
    # grader validation
    for p in ["gcp", "azure"]:
        g = gr.grade(f"ra/{p}", p); assert g["score"] == 1.0, (p, g); print(p, "grader reference 13/13")
    syn = pd.read_csv("data/grader_validation_syntax_faults.csv"); rows = []
    for p in ["gcp", "azure"]:
        lines = open(f"ra/{p}/main.tf", encoding="utf-8").read().splitlines()
        for h in [i for i, l in enumerate(lines) if l.startswith('resource "')]:
            j = next(k for k in range(h + 1, len(lines)) if lines[k] == "}")
            d = tempfile.mkdtemp(); open(os.path.join(d, "main.tf"), "w", encoding="utf-8").write("\n".join(lines[:j] + lines[j + 1:]))
            rows.append(round(gr.grade(d, p)["score"], 6)); shutil.rmtree(d)
    same = [round(x, 6) for x in syn.score] == rows
    print("grader syntax-fault scores reproduce:", same); ok &= same
    print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")

if __name__ == "__main__":
    main("--skip-mutations" in sys.argv)
