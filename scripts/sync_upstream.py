#!/usr/bin/env python3
"""Rebase the maintained fork branches, then update their refs atomically."""

import argparse
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{result.stdout}{result.stderr}")
    return result.stdout.strip()


def synchronize(repo, upstream, remote="origin", dry_run=False, record_check=False):
    """Stage all rebases before an atomic, lease-guarded push."""
    repo = Path(repo).resolve()
    if git(repo, "status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("Tracked local changes must be committed before synchronization")

    branches = ("main", "usb-respeaker", "pi0w")
    git(repo, "fetch", "--no-tags", remote)
    old = {name: git(repo, "rev-parse", f"refs/remotes/{remote}/{name}") for name in branches}
    alias = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", f"refs/remotes/{remote}/pi02w"],
        text=True,
        capture_output=True,
        check=False,
    )
    if alias.returncode == 0:
        old["pi02w"] = alias.stdout.strip()
        if old["pi02w"] != old["pi0w"]:
            raise RuntimeError("pi02w has diverged from pi0w; preserve its changes before synchronizing")

    git(repo, "fetch", "--no-tags", upstream, "main")
    upstream_sha = git(repo, "rev-parse", "FETCH_HEAD")
    staged = {}
    worktrees = []
    try:
        with tempfile.TemporaryDirectory(prefix="lva-upstream-") as folder:
            try:
                for branch in branches:
                    worktree = Path(folder) / branch
                    git(repo, "worktree", "add", "--detach", str(worktree), old[branch])
                    worktrees.append(worktree)
                    if branch == "main":
                        git(worktree, "rebase", "--rebase-merges", upstream_sha)
                        if record_check:
                            _record_upstream_check(worktree, upstream_sha)
                    else:
                        base = git(repo, "merge-base", old["main"], old[branch])
                        git(worktree, "rebase", "--rebase-merges", "--onto", staged["main"], base)
                    staged[branch] = git(worktree, "rev-parse", "HEAD")
                    git(worktree, "merge-base", "--is-ancestor", upstream_sha, "HEAD")
                if "pi02w" in old:
                    staged["pi02w"] = staged["pi0w"]

                changed = [branch for branch in staged if staged[branch] != old[branch]]
                if changed and not dry_run:
                    leases = [f"--force-with-lease=refs/heads/{branch}:{old[branch]}" for branch in changed]
                    refs = [f"{staged[branch]}:refs/heads/{branch}" for branch in changed]
                    git(repo, "push", "--atomic", *leases, remote, *refs)
            finally:
                for worktree in reversed(worktrees):
                    subprocess.run(
                        ["git", "-C", str(worktree), "rebase", "--abort"],
                        capture_output=True,
                        check=False,
                    )
                    git(repo, "worktree", "remove", "--force", str(worktree))
    except RuntimeError as error:
        raise RuntimeError("Synchronization stopped. Updates use an atomic, lease-guarded push; " f"inspect remote branch heads before retrying.\n{error}") from error

    return {"upstream": upstream_sha, "refs": staged, "previous": old, "changed": bool(changed), "dry_run": dry_run}


def _record_upstream_check(repo, upstream_sha):
    """Record source provenance without creating repeated same-month commits."""
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    path = Path(repo) / "maintenance" / "upstream-check.json"
    content = json.dumps({"upstream": upstream_sha, "checked_month": month}, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    git(repo, "add", "maintenance/upstream-check.json")
    git(repo, "commit", "--message", f"Record upstream source check for {month}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--upstream", default="https://github.com/OHF-Voice/linux-voice-assistant.git")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--record-check", action="store_true", help="Record the checked upstream SHA and UTC month in the synchronized branches")
    args = parser.parse_args()
    print(json.dumps(synchronize(args.repo, args.upstream, args.remote, args.dry_run, args.record_check)))


if __name__ == "__main__":
    main()
