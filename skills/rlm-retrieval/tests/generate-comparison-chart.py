#!/usr/bin/env python3
"""
Generate comparison charts for RLM vs Semantic vs Hybrid accuracy.
"""

import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

TESTS_DIR = Path(__file__).parent

def load_results():
    """Load results from all three modes."""
    results = {}
    for mode in ["rlm", "semantic", "hybrid"]:
        path = TESTS_DIR / f"baseline-results-2000-{mode}.json"
        if path.exists():
            with open(path) as f:
                results[mode] = json.load(f)
    return results

def compute_scores(results):
    """Compute scores by category for each mode."""
    scores = {}
    
    for mode, data in results.items():
        by_category = {}
        for r in data["results"]:
            cat = r["category"]
            if cat not in by_category:
                by_category[cat] = {"total": 0, "passed": 0}
            by_category[cat]["total"] += 1
            if r["indicatorShown"] == r["expected"]:
                by_category[cat]["passed"] += 1
        
        scores[mode] = by_category
    
    return scores

def generate_comparison_bar_chart(scores, total=4000):
    """Generate grouped bar chart comparing all three modes."""
    categories = sorted(set(
        cat for mode_scores in scores.values() 
        for cat in mode_scores.keys()
    ))
    
    modes = ["rlm", "semantic", "hybrid"]
    mode_labels = ["RLM (keyword)", "Semantic (embedding)", "Hybrid (both)"]
    colors = ["#3498db", "#9b59b6", "#2ecc71"]
    
    x = np.arange(len(categories))
    width = 0.25
    
    fig, ax = plt.subplots(figsize=(14, 6))
    
    for i, (mode, label, color) in enumerate(zip(modes, mode_labels, colors)):
        rates = []
        for cat in categories:
            if cat in scores.get(mode, {}):
                data = scores[mode][cat]
                rate = data["passed"] / data["total"] * 100 if data["total"] > 0 else 0
            else:
                rate = 0
            rates.append(rate)
        
        bars = ax.bar(x + i * width, rates, width, label=label, color=color, alpha=0.8)
        
        # Add value labels on bars
        for bar, rate in zip(bars, rates):
            if rate > 0:
                ax.annotate(f'{rate:.0f}%',
                           xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                           xytext=(0, 3),
                           textcoords="offset points",
                           ha='center', va='bottom', fontsize=7, rotation=90)
    
    ax.set_xlabel('Category', fontsize=12)
    ax.set_ylabel('Accuracy (%)', fontsize=12)
    ax.set_title(f'Context Memory: RLM vs Semantic vs Hybrid\n({total} test cases)', fontsize=16, fontweight='bold')
    ax.set_xticks(x + width)
    ax.set_xticklabels(categories, rotation=45, ha='right')
    ax.legend(loc='upper right')
    ax.set_ylim(0, 115)
    ax.axhline(y=80, color='gray', linestyle='--', alpha=0.5, label='80% threshold')
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(TESTS_DIR / "results-comparison.png", dpi=150)
    plt.savefig(TESTS_DIR / "results-comparison.svg")
    print(f"✅ Saved results-comparison.png/svg")

def generate_overall_comparison(scores):
    """Generate simple bar chart of overall accuracy."""
    modes = ["rlm", "semantic", "hybrid"]
    mode_labels = ["RLM\n(keyword)", "Semantic\n(embedding)", "Hybrid\n(both)"]
    colors = ["#3498db", "#9b59b6", "#2ecc71"]
    
    totals = []
    for mode in modes:
        mode_total = sum(d["total"] for d in scores.get(mode, {}).values())
        passed = sum(d["passed"] for d in scores.get(mode, {}).values())
        rate = passed / mode_total * 100 if mode_total > 0 else 0
        totals.append((rate, passed, mode_total))
    
    test_count = totals[0][2] if totals else 4000  # Get total from first mode
    
    fig, ax = plt.subplots(figsize=(8, 6))
    
    bars = ax.bar(mode_labels, [t[0] for t in totals], color=colors, alpha=0.8, edgecolor='black')
    
    # Add value labels
    for bar, (rate, passed, total) in zip(bars, totals):
        ax.annotate(f'{rate:.1f}%\n({passed}/{total})',
                   xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                   xytext=(0, 5),
                   textcoords="offset points",
                   ha='center', va='bottom', fontsize=12, fontweight='bold')
    
    ax.set_ylabel('Accuracy (%)', fontsize=12)
    ax.set_title(f'Overall Retrieval Accuracy\n({test_count} test cases)', fontsize=14, fontweight='bold')
    ax.set_ylim(0, 110)
    ax.axhline(y=80, color='gray', linestyle='--', alpha=0.5)
    ax.grid(axis='y', alpha=0.3)
    
    # Highlight winner
    winner_idx = max(range(len(totals)), key=lambda i: totals[i][0])
    bars[winner_idx].set_edgecolor('#27ae60')
    bars[winner_idx].set_linewidth(3)
    
    plt.tight_layout()
    plt.savefig(TESTS_DIR / "results-overall.png", dpi=150)
    plt.savefig(TESTS_DIR / "results-overall.svg")
    print(f"✅ Saved results-overall.png/svg")

def generate_heatmap(scores):
    """Generate heatmap showing accuracy by category and mode."""
    categories = sorted(set(
        cat for mode_scores in scores.values() 
        for cat in mode_scores.keys()
    ))
    modes = ["rlm", "semantic", "hybrid"]
    mode_labels = ["RLM", "Semantic", "Hybrid"]
    
    # Build matrix
    matrix = []
    for mode in modes:
        row = []
        for cat in categories:
            if cat in scores.get(mode, {}):
                data = scores[mode][cat]
                rate = data["passed"] / data["total"] * 100 if data["total"] > 0 else 0
            else:
                rate = 0
            row.append(rate)
        matrix.append(row)
    
    matrix = np.array(matrix)
    
    fig, ax = plt.subplots(figsize=(12, 4))
    
    im = ax.imshow(matrix, cmap='RdYlGn', aspect='auto', vmin=0, vmax=100)
    
    ax.set_xticks(np.arange(len(categories)))
    ax.set_yticks(np.arange(len(modes)))
    ax.set_xticklabels(categories, rotation=45, ha='right')
    ax.set_yticklabels(mode_labels)
    
    # Add text annotations
    for i in range(len(modes)):
        for j in range(len(categories)):
            value = matrix[i, j]
            color = 'white' if value < 50 else 'black'
            ax.text(j, i, f'{value:.0f}%', ha='center', va='center', color=color, fontsize=9)
    
    ax.set_title('Accuracy Heatmap by Category and Mode', fontsize=14, fontweight='bold')
    
    cbar = ax.figure.colorbar(im, ax=ax)
    cbar.ax.set_ylabel('Accuracy (%)', rotation=-90, va='bottom')
    
    plt.tight_layout()
    plt.savefig(TESTS_DIR / "results-heatmap.png", dpi=150)
    plt.savefig(TESTS_DIR / "results-heatmap.svg")
    print(f"✅ Saved results-heatmap.png/svg")

def generate_strengths_chart(scores):
    """Generate chart showing where each method wins."""
    categories = sorted(set(
        cat for mode_scores in scores.values() 
        for cat in mode_scores.keys()
    ))
    modes = ["rlm", "semantic", "hybrid"]
    
    # Find winner per category
    winners = {}
    for cat in categories:
        best_mode = None
        best_rate = -1
        for mode in modes:
            if cat in scores.get(mode, {}):
                data = scores[mode][cat]
                rate = data["passed"] / data["total"] * 100 if data["total"] > 0 else 0
                if rate > best_rate:
                    best_rate = rate
                    best_mode = mode
        winners[cat] = (best_mode, best_rate)
    
    # Count wins
    win_counts = {"rlm": 0, "semantic": 0, "hybrid": 0, "tie": 0}
    for cat, (winner, rate) in winners.items():
        # Check for ties
        rates = []
        for mode in modes:
            if cat in scores.get(mode, {}):
                data = scores[mode][cat]
                r = data["passed"] / data["total"] * 100 if data["total"] > 0 else 0
                rates.append((mode, r))
        
        max_rate = max(r for _, r in rates)
        tied = [m for m, r in rates if r == max_rate]
        
        if len(tied) > 1:
            win_counts["tie"] += 1
        else:
            win_counts[winner] += 1
    
    # Print summary
    print("\n📊 Category wins:")
    print(f"  RLM:      {win_counts['rlm']} categories")
    print(f"  Semantic: {win_counts['semantic']} categories")
    print(f"  Hybrid:   {win_counts['hybrid']} categories")
    print(f"  Tied:     {win_counts['tie']} categories")

def main():
    print("📊 Generating comparison charts...")
    
    results = load_results()
    if len(results) < 3:
        print("❌ Need results from all three modes. Run:")
        print("   python3 run-baseline-2000.py --mode compare")
        return
    
    scores = compute_scores(results)
    
    generate_comparison_bar_chart(scores)
    generate_overall_comparison(scores)
    generate_heatmap(scores)
    generate_strengths_chart(scores)
    
    print("\n✅ All charts generated!")

if __name__ == "__main__":
    main()
