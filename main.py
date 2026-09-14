"""
Main entry point for the Anheuser-Busch InBev (AB InBev) Enterprise Q&A Agent.

Usage:
  python3 main.py           # Launch interactive terminal chat
  python3 main.py --test    # Run offline test suite
"""
import sys
from pathlib import Path

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scripts.chat_cli import main as cli_main


def main():
    if len(sys.argv) > 1 and any(sys.argv[1] == flag for flag in ("--test-live", "-tl", "test-live")):
        import unittest
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromName("tests.test_live_llm")
        runner = unittest.TextTestRunner(verbosity=2)
        res = runner.run(suite)
        sys.exit(0 if res.wasSuccessful() else 1)
    elif len(sys.argv) > 1 and any(sys.argv[1] == flag for flag in ("--test-high-level", "-thl", "test-high-level")):
        import unittest
        loader = unittest.TestLoader()
        suite = loader.discover("tests/high_level")
        runner = unittest.TextTestRunner(verbosity=2)
        res = runner.run(suite)
        sys.exit(0 if res.wasSuccessful() else 1)
    elif len(sys.argv) > 1 and any(sys.argv[1] == flag for flag in ("--test-capabilities", "-tcap", "test-capabilities")):
        import unittest
        loader = unittest.TestLoader()
        suite = loader.discover("tests/capabilities")
        runner = unittest.TextTestRunner(verbosity=2)
        res = runner.run(suite)
        sys.exit(0 if res.wasSuccessful() else 1)
    elif len(sys.argv) > 1 and any(sys.argv[1] == flag for flag in ("--test-all", "-ta", "test-all")):
        import unittest
        loader = unittest.TestLoader()
        s1 = loader.discover("tests/high_level")
        s2 = loader.discover("tests/capabilities")
        s3 = loader.loadTestsFromName("tests.test_pipeline")
        full_suite = unittest.TestSuite([s1, s2, s3])
        runner = unittest.TextTestRunner(verbosity=2)
        res = runner.run(full_suite)
        sys.exit(0 if res.wasSuccessful() else 1)
    elif len(sys.argv) > 1 and any(sys.argv[1] == flag for flag in ("--test", "-t", "test")):
        import unittest
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromName("tests.test_pipeline")
        runner = unittest.TextTestRunner(verbosity=2)
        res = runner.run(suite)
        sys.exit(0 if res.wasSuccessful() else 1)
    else:
        cli_main()


if __name__ == "__main__":
    main()
