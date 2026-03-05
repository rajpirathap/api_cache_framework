"""
Configuration defaults for the Cache Admission Score (CAS) API response cache.
All can be overridden in Django settings as API_CACHE_FRAMEWORK = {...}.
"""
# Mean response size scale (bytes). 10 KB.
API_CACHE_S0_BYTES = 10 * 1024
# Std dev of response size scale (bytes). 5 KB.
API_CACHE_S1_BYTES = 5 * 1024
# Penalty weight for "frequent but low response size" (0.1 to 0.5).
API_CACHE_ALPHA = 0.2
# Asymmetric formula exponents (p=1,k=1,q=1 = original; p=2,k=1.2,q=1.5 = stronger anomaly rejection).
API_CACHE_P = 2.0
API_CACHE_K = 1.2
API_CACHE_Q = 1.5
# Minimum λ scale for volume term: CAS is reduced when λ is low (volume_term = λ/(λ+λ_min)).
API_CACHE_LAMBDA_MIN = 1.0
# Request count time window in minutes (for λ and σ_λ).
API_CACHE_WINDOW_MINUTES = 5
# Minimum CAS to admit a URL into cache. Below this we don't cache.
API_CACHE_SCORE_THRESHOLD = 0.3
# Default TTL for cached responses (minutes).
API_CACHE_DEFAULT_TTL_MINUTES = 20
# Max number of request timestamps to keep per key (sliding window).
API_CACHE_MAX_TIMESTAMPS_PER_KEY = 500
# Max number of response sizes to keep per key.
API_CACHE_MAX_SIZES_PER_KEY = 200
# Minimum total requests in the window before admitting to cache (cold-start guard).
API_CACHE_MIN_REQUESTS = 5
# Recency decay per window (0 = off). When > 0 (e.g. 0.9), recent windows count more.
API_CACHE_RECENCY_DECAY_PER_WINDOW = 0.0

# --- HTTP request queue middleware (CAS-priority) ---
# Max number of requests to hold in the priority queue.
API_QUEUE_MAX_SIZE = 1000
# Number of worker threads that process the queue (1 = strict priority order).
API_QUEUE_NUM_WORKERS = 1
# If True, reject with 503 when queue is full; if False, block until a slot is free.
API_QUEUE_REJECT_WHEN_FULL = True
# Default priority for keys with no history (first few requests).
API_QUEUE_DEFAULT_PRIORITY = 0.0
