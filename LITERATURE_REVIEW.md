# Literature Review: Cache Admission and Replacement Policies Compared to CAS

This document compares existing cache admission and eviction approaches in research and practice with the **Cache Admission Score (CAS)** formula used in this framework.

---

## 1. Scope and Terminology

- **Eviction policy:** Decides *which* item to remove when the cache is full (e.g. LRU, LFU).
- **Admission policy:** Decides *whether* to store an item at all when it is first (or again) requested (e.g. TinyLFU, CAS).
- **CAS** is a **score-based admission policy**: it computes a single number per URL from request frequency, traffic stability, response size, size stability, and a penalty for “frequent but small” responses; admission occurs only when the score exceeds a threshold and a minimum sample size is met.

---

## 2. Existing Approaches (Summary)

### 2.1 Eviction-Only Policies (No Explicit Admission)

**LRU (Least Recently Used)**  
- Evicts the least recently accessed item when space is needed.  
- Uses **recency** only; ignores frequency and size.  
- Widely used (e.g. Redis, Memcached, OS page caches).  
- Weak under one-hit wonders and scan traffic; can pollute the cache.

**LFU (Least Frequently Used)**  
- Evicts the item with the smallest access count.  
- Uses **frequency** only; no recency, no size.  
- Popular items can stay forever; slow to adapt when popularity shifts.

**LFUDA (LFU with Dynamic Aging)**  
- Adds a **global age** that increases on eviction; new items get the current age as base priority.  
- Combines **frequency + recency** (via aging) so old popular items can be evicted.  
- Still **eviction-focused**; no explicit admission and no size or cost.

**Comparison to CAS:** These policies do not decide “should we cache this URL?” up front; they cache on first access and only decide what to evict when full. CAS instead **blocks admission** until the score is high enough, so low-value URLs may never enter the cache.

---

### 2.2 Cost- and Size-Aware Eviction: GreedyDual-Size

**Source:** Cao & Irani, “Cost-Aware WWW Proxy Caching Algorithms,” USENIX USITS 1997; GreedyDual-Size (GD-Size).

**Idea:** Each cached object has a value **H = cost / size**. On access, H is set to this ratio (cost can be 1, latency, or network cost). When eviction is needed, the item with the **smallest H** is evicted. An “inflation” value L is used so that only the evicted item’s H is updated, giving O(log k) behavior.

**Factors:** **Cost** (e.g. fetch cost or latency), **size** (bytes), and **locality** (via when H is refreshed).  
**Admission:** Typically “admit on first access”; the policy is mainly **eviction**.  
**Size:** Explicit: large objects need higher cost to justify staying.

**Comparison to CAS:**  
- GD-Size is **eviction-centric** and uses a **ratio** (cost/size). CAS is **admission-centric** and uses a **multiplicative score minus a penalty**.  
- CAS uses **frequency and variance of request rate** (λ, σ_λ); GD-Size does not use request-rate statistics.  
- CAS uses **mean and variance of response size** (s̄, σ_s); GD-Size uses size but not size variance.  
- CAS explicitly **penalizes “frequent but small”** (α term); GD-Size penalizes low cost/size implicitly by evicting first.

---

### 2.3 Frequency-Based Admission: TinyLFU and W-TinyLFU

**Source:** TinyLFU (e.g. “TinyLFU: A Highly Efficient Cache Admission Policy”); W-TinyLFU extends it with a window and segments.

**Idea:** Maintain a compact **frequency sketch** (e.g. Count-Min Sketch) over recent requests. When a new item might replace an eviction victim, **admit the new item only if its estimated frequency is higher** than the victim’s. So admission is **explicit** and **frequency-based**. W-TinyLFU adds a small LRU window, probation/protected segments, and **periodic aging** (e.g. halving counts) to avoid stale popularity.

**Factors:** **Frequency** (estimated), **recency** (via aging and window).  
**Size:** Classic TinyLFU is **size-oblivious**; size-aware variants exist (e.g. size-aware TinyLFU in later work).  
**Admission:** Yes; admission is the main contribution.

**Comparison to CAS:**  
- Both use **admission** and **frequency**.  
- TinyLFU uses **estimated frequency** vs. **eviction victim**; CAS uses a **continuous score** vs. a **fixed threshold** and does not compare to a victim.  
- CAS uses **traffic stability (σ_λ)** and **size (s̄, σ_s)**; TinyLFU (base) does not.  
- CAS uses **mean size and size variance** and a **penalty for small responses**; TinyLFU does not (unless extended).  
- CAS can require **min_requests** (cold-start); TinyLFU uses a sketch that can be sparse early.

---

### 2.4 Size- and Hit-Rate-Aware CDN Policies: AdaptSize and Relatives

**Source:** AdaptSize (e.g. “AdaptSize: Orchestrating the Hot Object Memory Cache in a Content Delivery Network,” NSDI 2017); similar CDN-oriented work.

**Idea:** **Size-aware** cache admission/eviction for CDN hot object caches. Uses a **Markov-style cache model** to adapt parameters to object size distribution and request pattern. Aims to maximize object hit ratio (OHR) under variable object sizes.

**Factors:** **Size**, **request pattern** (modeled), **adaptation** to workload.  
**Admission/Eviction:** Often combined; size and hit-rate estimates drive both.  
**Reports:** Substantial OHR gains over default Nginx/Varnish in CDN traces.

**Comparison to CAS:**  
- Both are **size-aware** and **admission-aware**.  
- AdaptSize is **model-based and adaptive**; CAS is a **fixed formula** with tunable parameters (S₀, S₁, α, threshold).  
- CAS explicitly uses **frequency and variance of request rate** and **variance of response size**; AdaptSize uses size and pattern in a different (model-based) way.  
- CAS’s **penalty for “frequent but small”** is an explicit term; AdaptSize optimizes for hit ratio in a more global way.

---

### 2.5 Traffic Variance and Burstiness

**Variance reduction:** Work on “maximizing cache hit ratios by variance reduction” (e.g. Bernstein-based capacity constraints) uses **variance of cache occupancy** to control violation probability—different from request-rate variance but shows **variance** as a first-class concern in caching.

**Bursty/non-stationary traffic:** **d-TTL** and **f-TTL** (and similar) adapt TTL or use two-level caches to handle **non-stationary and bursty** request patterns. They treat **traffic pattern** (e.g. burstiness) as important; some use stochastic approximation to tune TTL.

**Comparison to CAS:**  
- CAS uses **σ_λ** (standard deviation of request count per window) as **traffic stability**. High σ_λ **reduces** the score, so bursty URLs are disadvantaged.  
- This aligns with the idea that **burstiness/variance** should affect caching decisions; CAS encodes it directly in the score via **λ/(1+σ_λ)** and in the use of **per-window counts**.

---

### 2.6 Learning-Based and Multi-Factor Policies

**RL-Cache (and similar):** Reinforcement learning for cache admission; uses **size, recency, frequency** (and sometimes other features). Optimizes hit rate or cost with respect to a reward; can adapt to different traffic classes and regions.

**Comparison to CAS:**  
- Both use **multiple factors** (frequency, size, etc.).  
- RL-Cache is **data-driven and adaptive**; CAS is a **hand-designed formula** with interpretable terms.  
- CAS adds **explicit variance terms** (σ_λ, σ_s) and a **closed-form penalty**; RL typically does not expose such a simple formula.

---

## 3. Comparison Table

| Dimension            | LRU / LFU / LFUDA | GreedyDual-Size | TinyLFU / W-TinyLFU | AdaptSize-style | CAS (this framework) |
|----------------------|-------------------|------------------|----------------------|-----------------|------------------------|
| **Primary role**     | Eviction           | Eviction         | Admission (+ eviction) | Admission/eviction | **Admission** |
| **Frequency**        | LFU/LFUDA only    | Indirect (locality) | Yes (sketch)     | Via model       | **Yes (λ)** |
| **Traffic stability**| No                | No               | No (aging only)      | Via model       | **Yes (σ_λ)** |
| **Recency**          | LRU; LFUDA aging   | Via H refresh    | Window + aging       | Implicit        | Optional (recency decay) |
| **Size**             | No                | Yes (cost/size)  | Optional in variants | Yes             | **Yes (s̄, S₀, S₁)** |
| **Size variance**    | No                | No               | No                   | Implicit        | **Yes (σ_s)** |
| **“Frequent but small” penalty** | No | Implicit (low H) | No                 | Implicit        | **Explicit (α term)** |
| **Cost/latency**     | No                | Yes (cost)       | No                   | Can be          | No (could be extended) |
| **Min sample / cold start** | No | No               | Sketch-based       | Model-based     | **Yes (min_requests)** |
| **Formula vs. learned** | Simple rule   | Closed formula   | Heuristic + sketch   | Model-based     | **Closed formula** |

---

## 4. Summary: How CAS Fits

- **Admission-first:** Like TinyLFU and AdaptSize, CAS is primarily about **when to cache**, not only what to evict.  
- **Multi-factor formula:** Combines **frequency (λ), traffic stability (σ_λ), mean size (s̄), size stability (σ_s),** and an **explicit penalty for frequent small responses (α)** in one expression.  
- **Explicit variance:** Using **σ_λ** and **σ_s** in the score is a clear difference from most classic policies (LRU, LFU, GD-Size, base TinyLFU), and aligns with work that stresses **variance and burstiness**.  
- **Size benefit g(s̄):** Rewards larger responses in the positive term; together with the penalty term, it makes “large = good, small = penalized” explicit, in a different way from GreedyDual-Size’s cost/size ratio.  
- **Cold-start:** **min_requests** avoids admitting on very few samples; similar in spirit to requiring enough data before trusting a model.  
- **Interpretability:** CAS is a **fixed, interpretable formula** with tunable parameters, unlike learning-based (e.g. RL-Cache) or black-box adaptive models.

Overall, CAS sits between **classic eviction policies** (LRU, LFU, GreedyDual-Size) and **modern admission/size-aware** work (TinyLFU, AdaptSize, RL-Cache), with a distinct emphasis on **request-rate and size variance** and an **explicit penalty for frequent small responses** in a single score.

---

## 5. References (Key Sources)

- Cao, P., & Irani, S. (1997). Cost-Aware WWW Proxy Caching Algorithms. USENIX USITS. (GreedyDual-Size.)  
- TinyLFU: A Highly Efficient Cache Admission Policy. ACM (e.g. 10.1145/3149371).  
- AdaptSize: Orchestrating the Hot Object Memory Cache in a Content Delivery Network. NSDI 2017.  
- LFU with Dynamic Aging (LFUDA); variance reduction and TTL-based caching for bursty traffic (e.g. d-TTL, f-TTL).  
- RL-Cache and similar learning-based cache admission (e.g. NSF PAR 10173191).

*(This review is for context and comparison; exact citations should be verified for formal use.)*
