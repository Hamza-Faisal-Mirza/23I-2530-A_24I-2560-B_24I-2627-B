"""Assemble the submission ZIP 23I-2530-A_24I-2560-B_24I-2627-B.zip.

    python tools/make_zip.py
"""
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "23I-2530-A_24I-2560-B_24I-2627-B"
FILES = ["cases.xlsx", "validation_report.txt", "approach.md", "approach_note.pdf", "proposal.pdf",
         "proposal.md", "repository.txt", "members.txt", "README.md", "requirements.txt", ".gitignore"]
DIRS = ["generator", "validator", "docs", "tools"]


def main():
    missing = [f for f in FILES if not os.path.exists(os.path.join(ROOT, f))]
    if missing:
        sys.exit(f"missing files: {missing}")
    if "REPLACE" in open(os.path.join(ROOT, "repository.txt")).read():
        print("WARNING: repository.txt still holds the placeholder link -- put the real GitHub URL in it "
              "and run this script again before submitting.")
    out = os.path.join(ROOT, NAME + ".zip")
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in FILES:
            z.write(os.path.join(ROOT, f), f"{NAME}/{f}")
            n += 1
        for d in DIRS:
            for base, dirs, files in os.walk(os.path.join(ROOT, d)):
                dirs[:] = sorted(x for x in dirs if x != "__pycache__")
                for f in sorted(files):
                    if f.endswith(".pyc") or f.startswith("~$"):
                        continue
                    full = os.path.join(base, f)
                    z.write(full, f"{NAME}/" + os.path.relpath(full, ROOT).replace(os.sep, "/"))
                    n += 1
    print(f"wrote {out} ({n} files, {os.path.getsize(out) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
