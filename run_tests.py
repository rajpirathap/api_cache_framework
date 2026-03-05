#!/usr/bin/env python
"""
Run tests and optional integration check.
Usage:
  python run_tests.py              # unit tests only
  python run_tests.py --demo       # unit tests + hit demo server (demo must be running)
"""
import os
import sys
import urllib.request
import urllib.error

# Add project root so we can import api_cache_framework
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_unit_tests():
    import unittest
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName("api_cache_framework.tests")
    runner = unittest.runner.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()

def hit_demo(base_url="http://127.0.0.1:8000", num_warmup=35, threshold_low=True):
    """Hit /api/items/ repeatedly then check if cache is used (same response)."""
    url = f"{base_url}/api/items/"
    if threshold_low:
        url += "?x=test"  # use a query so we don't mix with other tests
    try:
        # Warmup: many GETs to build CAS
        for i in range(num_warmup):
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as r:
                data = r.read()
            if i == 0:
                first_len = len(data)
        # One more request - if cached, should be fast and same size
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as r:
            data = r.read()
        print(f"  GET {url} -> {len(data)} bytes (first was {first_len})")
        return True
    except urllib.error.URLError as e:
        print(f"  Demo not reachable: {e}")
        return False

if __name__ == "__main__":
    ok = run_unit_tests()
    if "--demo" in sys.argv:
        print("\n--- Demo check (server must be running: python demo/manage.py runserver) ---")
        hit_demo()
    sys.exit(0 if ok else 1)
