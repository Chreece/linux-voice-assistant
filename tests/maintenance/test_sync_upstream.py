#!/usr/bin/env python3
"""Exercise upstream synchronization using isolated local Git repositories."""

import importlib.util
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "sync_upstream.py"
_SPEC = importlib.util.spec_from_file_location("lva_sync_upstream", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_SYNC = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_SYNC)


class SynchronizeUpstreamTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="lva-sync-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.upstream = self.root / "upstream.git"
        self.origin = self.root / "fork.git"
        self.seed = self.root / "seed"
        self.checkout = self.root / "checkout"
        self.git(self.root, "init", "--bare", "--initial-branch=main", str(self.upstream))
        self.git(self.root, "init", "--bare", "--initial-branch=main", str(self.origin))
        self.git(self.root, "init", "--initial-branch=main", str(self.seed))
        self.configure_identity(self.seed)
        self.commit("upstream.txt", "upstream baseline\n", "Initial upstream")
        self.commit("settings.txt", "upstream default\n", "Upstream settings")
        self.upstream_sha = self.git(self.seed, "rev-parse", "HEAD")
        self.git(self.seed, "remote", "add", "upstream", str(self.upstream))
        self.git(self.seed, "remote", "add", "origin", str(self.origin))
        self.git(self.seed, "push", "upstream", "main")

        self.commit("common-feature.txt", "shared customization\n", "Common customization")
        self.git(self.seed, "push", "origin", "main")
        self.git(self.seed, "switch", "--create", "usb-respeaker", "main")
        self.commit("usb-feature.txt", "LED customization\n", "USB LEDs")
        self.git(self.seed, "push", "origin", "usb-respeaker")
        self.git(self.seed, "switch", "--create", "pi0w", "main")
        self.commit("pi-profile.txt", "low-memory playback\n", "Pi profile")
        self.git(self.seed, "branch", "pi02w")
        self.git(self.seed, "push", "origin", "pi0w", "pi02w")
        self.git(self.root, "clone", str(self.origin), str(self.checkout))
        self.configure_identity(self.checkout)
        self.initial_worktrees = self.git(self.checkout, "worktree", "list", "--porcelain")

    def git(self, repo, *args):
        result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
        if result.returncode:
            self.fail(f"Git fixture command failed: {args!r}\n{result.stdout}{result.stderr}")
        return result.stdout.strip()

    def configure_identity(self, repo):
        self.git(repo, "config", "user.name", "LVA Sync Test")
        self.git(repo, "config", "user.email", "lva-sync-test@example.invalid")
        self.git(repo, "config", "commit.gpgsign", "false")

    def commit(self, filename, content, message):
        (self.seed / filename).write_text(content, encoding="utf-8")
        self.git(self.seed, "add", filename)
        self.git(self.seed, "commit", "--message", message)
        return self.git(self.seed, "rev-parse", "HEAD")

    def advance_upstream(self, filename="upstream.txt", content="new upstream behavior\n"):
        self.git(self.seed, "switch", "--detach", self.upstream_sha)
        self.upstream_sha = self.commit(filename, content, "New upstream change")
        self.git(self.seed, "push", "upstream", "HEAD:refs/heads/main")

    def remote_heads(self):
        lines = self.git(self.origin, "for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads")
        return dict(line.split() for line in lines.splitlines())

    def assert_checkout_preserved(self):
        self.assertEqual(self.git(self.checkout, "status", "--porcelain"), "")
        self.assertEqual(self.git(self.checkout, "worktree", "list", "--porcelain"), self.initial_worktrees)

    def test_rebases_shared_changes_and_keeps_each_variant_separate(self):
        old = self.remote_heads()
        self.advance_upstream()

        result = _SYNC.synchronize(self.checkout, str(self.upstream))

        heads = self.remote_heads()
        self.assertTrue(result["changed"])
        self.assertFalse(result["dry_run"])
        self.assertEqual(result["upstream"], self.upstream_sha)
        self.assertEqual(result["previous"], old)
        self.assertEqual(result["refs"], heads)
        for branch, sha in heads.items():
            self.git(self.origin, "merge-base", "--is-ancestor", self.upstream_sha, sha)
            self.assertEqual(self.git(self.origin, "show", f"{branch}:upstream.txt"), "new upstream behavior")
            self.assertEqual(self.git(self.origin, "show", f"{branch}:common-feature.txt"), "shared customization")
        self.assertEqual(self.git(self.origin, "diff", "--name-only", heads["main"], heads["usb-respeaker"]), "usb-feature.txt")
        self.assertEqual(self.git(self.origin, "diff", "--name-only", heads["main"], heads["pi0w"]), "pi-profile.txt")
        self.assertEqual(self.git(self.origin, "rev-list", "--count", f"{heads['main']}..{heads['usb-respeaker']}"), "1")
        self.assertEqual(self.git(self.origin, "rev-list", "--count", f"{heads['main']}..{heads['pi0w']}"), "1")
        self.assertEqual(heads["pi02w"], heads["pi0w"])
        self.assert_checkout_preserved()

    def test_variant_conflict_leaves_every_remote_branch_unchanged(self):
        self.git(self.seed, "switch", "usb-respeaker")
        self.commit("settings.txt", "USB-specific setting\n", "USB setting override")
        self.git(self.seed, "push", "origin", "usb-respeaker")
        self.advance_upstream("settings.txt", "changed upstream setting\n")
        old = self.remote_heads()

        with self.assertRaisesRegex(RuntimeError, "Synchronization stopped"):
            _SYNC.synchronize(self.checkout, str(self.upstream))

        self.assertEqual(self.remote_heads(), old)
        self.assert_checkout_preserved()

    def test_dry_run_stages_rebases_without_changing_remote_or_local_heads(self):
        self.advance_upstream()
        old = self.remote_heads()
        local_head = self.git(self.checkout, "rev-parse", "HEAD")

        result = _SYNC.synchronize(self.checkout, str(self.upstream), dry_run=True)

        self.assertTrue(result["changed"])
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["previous"], old)
        self.assertNotEqual(result["refs"]["main"], old["main"])
        self.assertEqual(self.remote_heads(), old)
        self.assertEqual(self.git(self.checkout, "rev-parse", "HEAD"), local_head)
        self.assert_checkout_preserved()

    def test_distinct_pi02w_changes_are_not_overwritten_by_alias_refresh(self):
        self.git(self.seed, "switch", "pi02w")
        self.commit("alias-only.txt", "unmerged existing Pi changes\n", "Pi compatibility branch work")
        self.git(self.seed, "push", "origin", "pi02w")
        self.advance_upstream()
        old = self.remote_heads()

        with self.assertRaisesRegex(RuntimeError, "pi02w has diverged"):
            _SYNC.synchronize(self.checkout, str(self.upstream))

        self.assertEqual(self.remote_heads(), old)
        self.assertEqual(self.git(self.origin, "show", "pi02w:alias-only.txt"), "unmerged existing Pi changes")
        self.assert_checkout_preserved()

    def test_concurrent_writer_rejects_the_entire_atomic_push(self):
        self.advance_upstream()
        self.git(self.seed, "switch", "main")
        writer_sha = self.commit("concurrent-user.txt", "new user change\n", "Concurrent user change")
        self.git(self.seed, "push", "origin", "HEAD:refs/heads/concurrent-writer")
        old = self.remote_heads()
        hook = self.checkout / ".git" / "hooks" / "pre-push"
        hook.write_text(
            "#!/bin/sh\n" + "exec git --git-dir=" + shlex.quote(str(self.origin)) + " update-ref refs/heads/main " + shlex.quote(writer_sha) + " " + shlex.quote(old["main"]) + "\n",
            encoding="utf-8",
        )
        hook.chmod(0o755)

        with self.assertRaisesRegex(RuntimeError, "Synchronization stopped"):
            _SYNC.synchronize(self.checkout, str(self.upstream))

        expected = dict(old, main=writer_sha)
        self.assertEqual(self.remote_heads(), expected)
        self.assert_checkout_preserved()


if __name__ == "__main__":
    unittest.main()
