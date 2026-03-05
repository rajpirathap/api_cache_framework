"""
Parameterized synthetic data generator for CAS-based anomaly evaluation.

Generates labeled datasets with known (λ, σ_λ, mean_size, σ_s) for each scenario.
No Django or StatsCollector required — produces raw stats directly for evaluation.
"""
from dataclasses import dataclass
from typing import Iterator

# CAS formula defaults (bytes)
S0 = 10 * 1024
S1 = 5 * 1024
ALPHA = 0.2
# Asymmetric formula exponents (p=2, k=1.2, q=1.5 for stronger anomaly rejection)
P = 2.0
K = 1.2
Q = 1.5
# Low-volume term: reduce CAS when λ < lambda_min (volume_term = λ/(λ+λ_min))
LAMBDA_MIN = 1.0


@dataclass
class SyntheticEndpoint:
    """Single labeled endpoint for evaluation."""
    scenario: str
    label: int  # 0 = normal, 1 = anomaly
    lambda_: float
    sigma_lambda: float
    mean_size: float
    sigma_size: float
    total_requests: int
    description: str


def generate_normal() -> Iterator[SyntheticEndpoint]:
    """Normal traffic: high CAS expected."""
    yield SyntheticEndpoint(
        scenario="normal",
        label=0,
        lambda_=10.0,
        sigma_lambda=1.0,
        mean_size=50 * 1024,
        sigma_size=500.0,
        total_requests=120,
        description="high freq, low variance, large responses",
    )
    yield SyntheticEndpoint(
        scenario="normal",
        label=0,
        lambda_=8.0,
        sigma_lambda=0.5,
        mean_size=30 * 1024,
        sigma_size=200.0,
        total_requests=100,
        description="stable traffic, medium-large payloads",
    )
    yield SyntheticEndpoint(
        scenario="normal",
        label=0,
        lambda_=15.0,
        sigma_lambda=2.0,
        mean_size=100 * 1024,
        sigma_size=1000.0,
        total_requests=150,
        description="high freq, large payloads",
    )
    yield SyntheticEndpoint(
        scenario="normal",
        label=0,
        lambda_=5.0,
        sigma_lambda=0.8,
        mean_size=20 * 1024,
        sigma_size=300.0,
        total_requests=80,
        description="moderate stable traffic",
    )
    yield SyntheticEndpoint(
        scenario="normal",
        label=0,
        lambda_=12.0,
        sigma_lambda=1.5,
        mean_size=40 * 1024,
        sigma_size=400.0,
        total_requests=130,
        description="steady high-traffic API",
    )


def generate_frequent_small() -> Iterator[SyntheticEndpoint]:
    """Frequent + small responses: DoS/abuse pattern, low CAS."""
    yield SyntheticEndpoint(
        scenario="frequent_small",
        label=1,
        lambda_=8.0,
        sigma_lambda=1.0,
        mean_size=200.0,
        sigma_size=50.0,
        total_requests=100,
        description="high rate + tiny responses",
    )
    yield SyntheticEndpoint(
        scenario="frequent_small",
        label=1,
        lambda_=12.0,
        sigma_lambda=2.0,
        mean_size=500.0,
        sigma_size=100.0,
        total_requests=150,
        description="very frequent, small payloads",
    )
    yield SyntheticEndpoint(
        scenario="frequent_small",
        label=1,
        lambda_=5.0,
        sigma_lambda=0.5,
        mean_size=800.0,
        sigma_size=200.0,
        total_requests=80,
        description="moderate freq, small responses",
    )
    yield SyntheticEndpoint(
        scenario="frequent_small",
        label=1,
        lambda_=20.0,
        sigma_lambda=3.0,
        mean_size=100.0,
        sigma_size=20.0,
        total_requests=200,
        description="extremely frequent tiny responses",
    )
    yield SyntheticEndpoint(
        scenario="frequent_small",
        label=1,
        lambda_=6.0,
        sigma_lambda=1.0,
        mean_size=400.0,
        sigma_size=80.0,
        total_requests=90,
        description="frequent small API hits",
    )


def generate_bursty() -> Iterator[SyntheticEndpoint]:
    """Bursty traffic: high σ_λ vs λ, term1 suppressed."""
    yield SyntheticEndpoint(
        scenario="bursty",
        label=1,
        lambda_=5.0,
        sigma_lambda=25.0,
        mean_size=10 * 1024,
        sigma_size=500.0,
        total_requests=100,
        description="high traffic instability",
    )
    yield SyntheticEndpoint(
        scenario="bursty",
        label=1,
        lambda_=3.0,
        sigma_lambda=12.0,
        mean_size=5 * 1024,
        sigma_size=200.0,
        total_requests=80,
        description="moderate mean, very variable counts",
    )
    yield SyntheticEndpoint(
        scenario="bursty",
        label=1,
        lambda_=8.0,
        sigma_lambda=40.0,
        mean_size=15 * 1024,
        sigma_size=300.0,
        total_requests=120,
        description="bursty high-traffic pattern",
    )
    yield SyntheticEndpoint(
        scenario="bursty",
        label=1,
        lambda_=2.0,
        sigma_lambda=10.0,
        mean_size=8 * 1024,
        sigma_size=100.0,
        total_requests=60,
        description="low mean, highly variable",
    )
    yield SyntheticEndpoint(
        scenario="bursty",
        label=1,
        lambda_=4.0,
        sigma_lambda=18.0,
        mean_size=12 * 1024,
        sigma_size=400.0,
        total_requests=90,
        description="bursty pattern",
    )


def generate_erratic_size() -> Iterator[SyntheticEndpoint]:
    """Erratic response sizes: high σ_s vs mean_size, term3 suppressed."""
    yield SyntheticEndpoint(
        scenario="erratic_size",
        label=1,
        lambda_=6.0,
        sigma_lambda=1.0,
        mean_size=500.0,
        sigma_size=3000.0,
        total_requests=100,
        description="high size variance",
    )
    yield SyntheticEndpoint(
        scenario="erratic_size",
        label=1,
        lambda_=4.0,
        sigma_lambda=0.8,
        mean_size=200.0,
        sigma_size=1500.0,
        total_requests=80,
        description="small mean, huge size variance",
    )
    yield SyntheticEndpoint(
        scenario="erratic_size",
        label=1,
        lambda_=8.0,
        sigma_lambda=2.0,
        mean_size=1000.0,
        sigma_size=5000.0,
        total_requests=120,
        description="erratic payload sizes",
    )
    yield SyntheticEndpoint(
        scenario="erratic_size",
        label=1,
        lambda_=5.0,
        sigma_lambda=1.0,
        mean_size=300.0,
        sigma_size=2000.0,
        total_requests=90,
        description="variable response sizes",
    )
    yield SyntheticEndpoint(
        scenario="erratic_size",
        label=1,
        lambda_=7.0,
        sigma_lambda=1.5,
        mean_size=400.0,
        sigma_size=2500.0,
        total_requests=110,
        description="highly variable sizes",
    )


def generate_low_cas() -> Iterator[SyntheticEndpoint]:
    """Generic low CAS: combination of factors, no single dominant pattern."""
    yield SyntheticEndpoint(
        scenario="low_cas",
        label=1,
        lambda_=4.0,
        sigma_lambda=2.0,
        mean_size=1024.0,
        sigma_size=800.0,
        total_requests=80,
        description="mild penalty + moderate variance",
    )
    yield SyntheticEndpoint(
        scenario="low_cas",
        label=1,
        lambda_=6.0,
        sigma_lambda=4.0,
        mean_size=600.0,
        sigma_size=500.0,
        total_requests=100,
        description="several factors suppress CAS",
    )
    yield SyntheticEndpoint(
        scenario="low_cas",
        label=1,
        lambda_=3.0,
        sigma_lambda=1.5,
        mean_size=500.0,
        sigma_size=600.0,
        total_requests=60,
        description="low score, mixed causes",
    )


def generate_all() -> list[SyntheticEndpoint]:
    """Generate full labeled dataset."""
    out: list[SyntheticEndpoint] = []
    for gen in (generate_normal, generate_frequent_small, generate_bursty, generate_erratic_size, generate_low_cas):
        out.extend(gen())
    return out


if __name__ == "__main__":
    data = generate_all()
    print(f"Generated {len(data)} synthetic endpoints")
    print(f"  Normal: {sum(1 for e in data if e.label == 0)}")
    print(f"  Anomaly: {sum(1 for e in data if e.label == 1)}")
    for e in data[:3]:
        print(f"  {e.scenario}: λ={e.lambda_}, σ_λ={e.sigma_lambda}, s̄={e.mean_size:.0f}, σ_s={e.sigma_size:.0f}")
