"""Temporary media hosting on the `media` branch of vivek291186/livelica.

The branch is always rebuilt as ONE commit, so files removed from it stop using space
(git history would otherwise keep every old video forever).

  python media.py add <local_folder> <dest_path>     e.g. add /tmp/out videos/2026-10-22-bearing-care
  python media.py remove <dest_path> [<dest_path> ...]
  python media.py list                               folders and their manifest.json
  python media.py url <dest_path>/<file>             public raw URL

Each task writes <dest_path>/manifest.json after scheduling:
  {"created": "YYYY-MM-DD", "source": "<article or product URL>",
   "posts": [{"metricool_id": 401549218, "network": "youtube", "date": "YYYY-MM-DD"}]}
The cleanup task deletes a folder only when every post in its manifest is confirmed live.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REMOTE = "https://github.com/vivek291186/livelica"
BRANCH = "media"
RAW = "https://raw.githubusercontent.com/vivek291186/livelica/media/"
GIT_ID = ["-c", "user.name=LiveLica Bot", "-c", "user.email=vivek291186@gmail.com"]
MSG = "Media branch\n\nCo-Authored-By: Claude <noreply@anthropic.com>"


def git(args, cwd, check=True):
    return subprocess.run(["git", *args], cwd=cwd, check=check, capture_output=True, text=True)


def checkout():
    """Fresh shallow checkout of the media branch in its own temp folder. Returns (dir, sha)."""
    d = Path(tempfile.mkdtemp(prefix="livelica-media-"))
    git(["init", "-q"], d)
    git(["remote", "add", "origin", REMOTE], d)
    git(["fetch", "-q", "--depth", "1", "origin", BRANCH], d)
    git(["checkout", "-q", "-B", BRANCH, "FETCH_HEAD"], d)
    sha = git(["rev-parse", "HEAD"], d).stdout.strip()
    return d, sha


def commit_and_push(d, sha):
    git(["add", "-A"], d)
    git([*GIT_ID, "commit", "-q", "--amend", "--allow-empty", "-m", MSG], d)
    r = git(["push", "-q", f"--force-with-lease={BRANCH}:{sha}", "origin", BRANCH], d, check=False)
    return r.returncode == 0, r.stderr


def mutate(fn, label):
    for attempt in range(4):
        d, sha = checkout()
        try:
            fn(d)
            ok, err = commit_and_push(d, sha)
            if ok:
                print(f"{label}: pushed")
                return
            print(f"{label}: push rejected (someone else pushed), retrying. {err.strip()[:200]}")
        finally:
            shutil.rmtree(d, ignore_errors=True)
    sys.exit(f"{label}: failed after 4 attempts")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "add":
        src, dest = Path(sys.argv[2]), sys.argv[3].strip("/")

        def fn(d):
            target = d / dest
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(src, target, ignore=shutil.ignore_patterns("*.webp", "__pycache__"))
        mutate(fn, f"add {dest}")
        for p in sorted(src.rglob("*")):
            if p.is_file():
                print(RAW + dest + "/" + str(p.relative_to(src)))
    elif cmd == "remove":
        dests = [x.strip("/") for x in sys.argv[2:]]

        def fn(d):
            for x in dests:
                shutil.rmtree(d / x, ignore_errors=True)
        mutate(fn, "remove " + ", ".join(dests))
    elif cmd == "list":
        d, _ = checkout()
        try:
            for m in sorted(d.rglob("manifest.json")):
                folder = str(m.parent.relative_to(d))
                print(json.dumps({"folder": folder, **json.loads(m.read_text())}))
            for top in sorted(p for p in d.iterdir() if p.is_dir() and p.name != ".git"):
                for f in sorted(x for x in top.iterdir() if x.is_dir()):
                    if not (f / "manifest.json").exists():
                        print(json.dumps({"folder": str(f.relative_to(d)), "manifest": None}))
        finally:
            shutil.rmtree(d, ignore_errors=True)
    elif cmd == "url":
        print(RAW + sys.argv[2].strip("/"))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
