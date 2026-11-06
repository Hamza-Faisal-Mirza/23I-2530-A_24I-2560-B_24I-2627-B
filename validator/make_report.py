"""Run the validator on cases.xlsx and on every copy in validator/tests/ and
write validation_report.txt (to the repository root and to validator/).

    python validator/make_report.py cases.xlsx
"""
import contextlib
import io
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import validate  # noqa: E402


def run(args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = validate.main(args)
    return code, buf.getvalue()


def main():
    master = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "cases.xlsx")
    out = []
    w = out.append
    w("LIFELINE -- validation report -- group 76 (seed 76)")
    w(f"generated {time.strftime('%Y-%m-%d %H:%M')} by validator/make_report.py")
    w("=" * 78)
    w("")
    w("PART 1. Master workbook cases.xlsx (full mode: all 50 cases + cross-case rules)")
    w("-" * 78)
    code, text = run([master, "--seed", "76"])
    w(text.rstrip())
    master_ok = code == 0
    w("")
    w("PART 2. Test copies in validator/tests/ (see validator/tests/manifest.txt)")
    w("-" * 78)
    rows, details = [], []
    with open(os.path.join(HERE, "tests", "manifest.txt")) as fh:
        manifest = [line.rstrip("\n").split("\t") for line in fh if line.strip()]
    all_ok = True
    for name, mode, expect, desc in manifest:
        path = os.path.join(HERE, "tests", name)
        args = [path, "--seed", "76"] + (["--partial"] if mode == "partial" else [])
        code, text = run(args)
        if expect == "PASS":
            verdict = "PASS" if code == 0 else "FAIL"
            ok = code == 0
        else:
            verdict = "REJECTED" if code != 0 else "ACCEPTED"
            ok = code != 0 and f"[{expect}]" in text
        all_ok &= ok
        rows.append((name, expect, verdict, "yes" if ok else "NO"))
        details.append((name, desc, expect, text))
    w(f"{'test copy':44} {'expected':9} {'validator':10} as expected")
    for name, expect, verdict, ok in rows:
        w(f"{name:44} {expect:9} {verdict:10} {ok}")
    w("")
    for name, desc, expect, text in details:
        w(f"--- {name}: {desc} (expected: {expect})")
        lines = [l for l in text.splitlines() if not l.endswith(" PASS") or expect == "PASS"]
        w("\n".join(lines).rstrip())
        w("")
    w("=" * 78)
    w(f"SUMMARY: master workbook {'PASS (50/50)' if master_ok else 'FAIL'}; "
      f"{sum(1 for r in rows if r[3] == 'yes')}/{len(rows)} test copies behaved as expected "
      f"({sum(1 for r in rows if r[1] == 'PASS')} valid copies passed, "
      f"{sum(1 for r in rows if r[1] != 'PASS' and r[3] == 'yes')} broken copies rejected "
      f"with the expected rule)")
    report = "\n".join(out) + "\n"
    for path in (os.path.join(ROOT, "validation_report.txt"), os.path.join(HERE, "validation_report.txt")):
        with open(path, "w") as fh:
            fh.write(report)
    print(report[-400:])
    return 0 if master_ok and all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
