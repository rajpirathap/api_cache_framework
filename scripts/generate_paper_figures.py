#!/usr/bin/env python
"""
Generate figures for the CAS paper (Computer Networks / JNCA).

Output: paper/figures/architecture.pdf, cas_distribution.pdf, unswnb15_metrics.pdf

Usage:
  python scripts/generate_paper_figures.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "api_cache_framework"))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
except ImportError:
    print("matplotlib required: pip install matplotlib")
    sys.exit(1)

FIG_DIR = os.path.join(ROOT, "paper", "figures")
os.makedirs(FIG_DIR, exist_ok=True)


def fig_architecture():
    """Framework architecture: stats -> CAS -> admission / anomaly / queue."""
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    ax.set_aspect("equal")
    ax.axis("off")

    # Colors
    c_input = "#e8f4f8"
    c_core = "#c8e6c9"
    c_output = "#fff9c4"
    c_box = "#37474f"
    ax.set_facecolor("#fafafa")

    def box(ax, xy, w, h, label, color=c_core, fontsize=9):
        r = FancyBboxPatch(xy, w, h, boxstyle="round,pad=0.02", facecolor=color, edgecolor=c_box, linewidth=1.2)
        ax.add_patch(r)
        ax.text(xy[0] + w / 2, xy[1] + h / 2, label, ha="center", va="center", fontsize=fontsize)

    def arrow(ax, start, end, color="#555"):
        ax.annotate("", xy=end, xytext=start, arrowprops=dict(arrowstyle="->", color=color, lw=1.5))

    # Top row: Stats collector
    box(ax, (1, 4), 2.2, 0.8, "Stats Collector\n(λ, σ_λ, s̄, σ_s)", c_input)
    box(ax, (4, 4), 2, 0.8, "CAS Formula", c_core)
    box(ax, (7, 4), 2, 0.8, "Decision\n(CAS ≥ θ ?)", c_core)

    arrow(ax, (3.2, 4.4), (4, 4.4))
    arrow(ax, (6, 4.4), (7, 4.4))

    # Bottom row: three outputs
    box(ax, (0.5, 1.5), 2.2, 0.9, "Cache Admission", c_output)
    box(ax, (3.8, 1.5), 2.2, 0.9, "Anomaly Detection", c_output)
    box(ax, (7.1, 1.5), 2.2, 0.9, "Request Queue", c_output)

    arrow(ax, (4.5, 3.6), (1.6, 2.4))
    arrow(ax, (5, 3.6), (4.9, 2.4))
    arrow(ax, (5.5, 3.6), (8.2, 2.4))

    ax.set_title("CAS Framework Architecture", fontsize=12, fontweight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "architecture.pdf"), bbox_inches="tight")
    plt.close()
    print(f"  {FIG_DIR}/architecture.pdf")


def fig_cas_distribution():
    """CAS score distribution by scenario (synthetic data)."""
    from score import cache_score
    from generate_synthetic_data import generate_all, S0, S1, ALPHA, P, K, Q

    data = list(generate_all())
    scenarios = {}
    for ep in data:
        cas = cache_score(
            lambda_=ep.lambda_, sigma_lambda=ep.sigma_lambda,
            mean_size=ep.mean_size, sigma_size=ep.sigma_size,
            s0=S0, s1=S1, alpha=ALPHA, p=P, k=K, q=Q,
        )
        s = ep.scenario
        if s not in scenarios:
            scenarios[s] = []
        scenarios[s].append((cas, ep.label))

    order = ["normal", "frequent_small", "bursty", "erratic_size", "low_cas"]
    labels = ["normal", "frequent_small", "bursty", "erratic_size", "low_cas"]
    colors = ["#4caf50", "#f44336", "#f44336", "#f44336", "#f44336"]

    fig, ax = plt.subplots(figsize=(6, 4))
    x_pos = []
    vals = []
    bar_colors = []
    for i, (s, lbl) in enumerate(zip(order, labels)):
        if s not in scenarios:
            continue
        cas_list = [c for c, _ in scenarios[s]]
        for j, c in enumerate(cas_list):
            x_pos.append(i + 0.2 * (j - len(cas_list) / 2 + 0.5))
            vals.append(c)
            bar_colors.append(colors[i])

    ax.scatter(x_pos, vals, c=bar_colors, s=40, alpha=0.8, edgecolors="#333")
    ax.axhline(y=0.05, color="#999", linestyle="--", linewidth=1, label="threshold (0.05)")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylabel("CAS score")
    ax.set_xlabel("Scenario")
    ax.set_title("CAS Distribution by Scenario (Synthetic Data)")
    ax.legend()
    ax.set_ylim(bottom=-0.1)
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "cas_distribution.pdf"), bbox_inches="tight")
    plt.close()
    print(f"  {FIG_DIR}/cas_distribution.pdf")


def fig_unswnb15_metrics():
    """UNSW-NB15 metrics: Precision, Recall, F1, Accuracy bar chart."""
    metrics = ["Precision", "Recall", "F1", "Accuracy"]
    values = [0.77, 0.09, 0.16, 0.12]
    _bar_metrics(metrics, values, "UNSW-NB15 (118 endpoints)", "unswnb15_metrics.pdf")


def _bar_metrics(metrics, values, title, filename):
    fig, ax = plt.subplots(figsize=(5, 3.5))
    bars = ax.bar(metrics, values, color=["#2196f3", "#ff9800", "#4caf50", "#9c27b0"], edgecolor="#333")
    ax.set_ylabel("Value")
    ax.set_title(title)
    ax.set_ylim(0, 1)
    for b, v in zip(bars, values):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.02, f"{v:.2f}", ha="center", fontsize=10)
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, filename), bbox_inches="tight")
    plt.close()
    print(f"  {FIG_DIR}/{filename}")


def fig_cicids_metrics():
    """CICIDS2017 metrics bar chart."""
    metrics = ["Precision", "Recall", "F1", "Accuracy"]
    values = [0.25, 1.0, 0.40, 0.995]
    _bar_metrics(metrics, values, "CICIDS2017 (634 endpoints)", "cicids_metrics.pdf")


def main():
    print("Generating paper figures...")
    fig_architecture()
    fig_cas_distribution()
    fig_unswnb15_metrics()
    fig_cicids_metrics()
    print("Done.")


if __name__ == "__main__":
    main()
