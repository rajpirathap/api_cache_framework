"""
Unit tests for Cache Admission Score (CAS) formula and stats.
"""
import math
import unittest

from .score import cache_score, cache_score_breakdown, compute_lambda_sigma, should_cache
from .stats import RequestStats, StatsCollector


class TestComputeLambdaSigma(unittest.TestCase):
    def test_empty_returns_zero(self):
        self.assertEqual(compute_lambda_sigma([]), (0.0, 0.0))

    def test_single_value(self):
        lam, sig = compute_lambda_sigma([5])
        self.assertEqual(lam, 5.0)
        self.assertEqual(sig, 0.0)

    def test_uniform_counts(self):
        counts = [10, 10, 10, 10]
        lam, sig = compute_lambda_sigma(counts)
        self.assertAlmostEqual(lam, 10.0)
        self.assertAlmostEqual(sig, 0.0)

    def test_varying_counts(self):
        counts = [1, 2, 3, 4, 5]
        lam, sig = compute_lambda_sigma(counts)
        self.assertAlmostEqual(lam, 3.0)
        self.assertGreater(sig, 0.0)
        # population std dev of [1,2,3,4,5] is sqrt(2)
        self.assertAlmostEqual(sig, math.sqrt(2.0))


class TestCacheScore(unittest.TestCase):
    def test_zero_lambda_returns_zero(self):
        self.assertEqual(
            cache_score(0.0, 1.0, 1000.0, 0.0, 10240.0, 5120.0, 0.2), 0.0
        )

    def test_high_freq_low_variance_large_size_positive(self):
        # High λ, low σ_λ, large s̄ -> good for cache
        s = cache_score(
            lambda_=10.0,
            sigma_lambda=0.5,
            mean_size=50 * 1024,  # 50 KB
            sigma_size=100.0,
            s0=10 * 1024,
            s1=5 * 1024,
            alpha=0.2,
        )
        self.assertGreater(s, 0.0)
        self.assertGreater(s, 0.3)

    def test_penalty_reduces_score_for_small_size(self):
        # Penalty term α*λ*S_0/(s̄+S_0) is larger for small s̄, so increasing alpha
        # should reduce score more. Use a size where low alpha still gives positive score.
        s_low_alpha = cache_score(
            lambda_=10.0,
            sigma_lambda=0.5,
            mean_size=2000,
            sigma_size=0.0,
            s0=10 * 1024,
            s1=5 * 1024,
            alpha=0.1,
        )
        s_high_alpha = cache_score(
            lambda_=10.0,
            sigma_lambda=0.5,
            mean_size=2000,
            sigma_size=0.0,
            s0=10 * 1024,
            s1=5 * 1024,
            alpha=0.5,
        )
        self.assertLess(s_high_alpha, s_low_alpha)

    def test_negative_raw_clamped_to_zero(self):
        s = cache_score(
            lambda_=1.0,
            sigma_lambda=100.0,
            mean_size=100.0,
            sigma_size=0.0,
            s0=10 * 1024,
            s1=5 * 1024,
            alpha=0.5,
        )
        self.assertEqual(s, 0.0)

    def test_low_volume_reduces_cas(self):
        # volume_term = λ/(λ+λ_min): low λ should give lower CAS
        b_low = cache_score_breakdown(
            lambda_=0.5,
            sigma_lambda=0.1,
            mean_size=20 * 1024,
            sigma_size=0.0,
            s0=10 * 1024,
            s1=5 * 1024,
            alpha=0.2,
            lambda_min=1.0,
        )
        b_high = cache_score_breakdown(
            lambda_=10.0,
            sigma_lambda=0.1,
            mean_size=20 * 1024,
            sigma_size=0.0,
            s0=10 * 1024,
            s1=5 * 1024,
            alpha=0.2,
            lambda_min=1.0,
        )
        self.assertLess(b_low["volume_term"], b_high["volume_term"])
        self.assertLess(b_low["final"], b_high["final"])


class TestShouldCache(unittest.TestCase):
    def test_below_threshold_returns_false(self):
        # Low counts -> low λ -> low score
        self.assertFalse(
            should_cache(
                counts_per_window=[0, 0, 1, 0],
                mean_size=10000.0,
                sigma_size=0.0,
                s0=10 * 1024,
                s1=5 * 1024,
                alpha=0.2,
                threshold=0.3,
            )
        )

    def test_above_threshold_returns_true(self):
        # Many uniform counts + large size can exceed threshold
        counts = [20] * 12  # 20 per window, uniform
        self.assertTrue(
            should_cache(
                counts_per_window=counts,
                mean_size=30 * 1024,
                sigma_size=0.0,
                s0=10 * 1024,
                s1=5 * 1024,
                alpha=0.2,
                threshold=0.3,
            )
        )

    def test_min_requests_blocks_until_enough_data(self):
        # Even high score is rejected if total requests < min_requests
        counts = [10, 10]  # only 20 requests total; if min_requests=25, reject
        self.assertFalse(
            should_cache(
                counts_per_window=counts,
                mean_size=30 * 1024,
                sigma_size=0.0,
                s0=10 * 1024,
                s1=5 * 1024,
                alpha=0.2,
                threshold=0.3,
                min_requests=25,
            )
        )
        self.assertTrue(
            should_cache(
                counts_per_window=counts,
                mean_size=30 * 1024,
                sigma_size=0.0,
                s0=10 * 1024,
                s1=5 * 1024,
                alpha=0.2,
                threshold=0.3,
                min_requests=5,
            )
        )


class TestRequestStats(unittest.TestCase):
    def test_record_and_size_stats(self):
        r = RequestStats(max_timestamps=10, max_sizes=10)
        r.record(100)
        r.record(200)
        r.record(300)
        mean_s, std_s = r.get_size_stats()
        self.assertAlmostEqual(mean_s, 200.0)
        self.assertAlmostEqual(std_s, 81.65, places=1)

    def test_counts_per_window(self):
        import unittest.mock
        base_time = 1000000.0
        with unittest.mock.patch("api_cache_framework.stats.time") as mtime:
            # 3 calls during record(), 1 during get_request_counts_per_window
            mtime.time.side_effect = [
                base_time,
                base_time + 0.1,
                base_time + 0.2,
                base_time + 30,  # "now" when computing windows
            ]
            r = RequestStats(max_timestamps=20, max_sizes=20)
            for _ in range(3):
                r.record(1000)
            counts = r.get_request_counts_per_window(
                window_seconds=60.0, num_windows=5
            )
        self.assertEqual(len(counts), 5)
        self.assertEqual(sum(counts), 3, "all 3 requests should fall in one window")


if __name__ == "__main__":
    unittest.main()
