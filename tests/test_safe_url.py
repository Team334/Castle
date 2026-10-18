"""Login redirect target validation; request context only, no database."""
import unittest

from flask import Flask

from app.utils import is_safe_url


class SafeUrlTests(unittest.TestCase):
    def test_only_same_host_relative_targets_are_safe(self):
        with Flask(__name__).test_request_context(base_url="https://castle.test/"):
            for target in ["/scouting", "/team/view/334?tab=1"]:
                self.assertTrue(is_safe_url(target), target)
            # Absolute URLs are rejected even on the same host (they contain "//")
            for target in ["", None, "https://castle.test/leaderboard", "https://evil.test/", "//evil.test/", "/\\evil.test", "/a/../b",
                           "javascript:alert(1)"]:
                self.assertFalse(is_safe_url(target), target)


if __name__ == '__main__':
    unittest.main()
