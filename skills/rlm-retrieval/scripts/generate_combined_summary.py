#!/usr/bin/env python3
"""Generate a combined summary chart showing all validation metrics."""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# Data from our validation
data = {
    "Unit Tests": {
        "OpenClaw/Clawdbot": {"tests": 4000, "accuracy": 99.8},
        "Claude Code": {"tests": 4457, "accuracy": 99.98},
    },
    "Live Validation": {
        "OpenClaw (session queries)": {"tests": 71, "accuracy": 93.0},
        "Claude Code": {"tests": 52, "accuracy": 100.0},
    },
    "Category Breakdown (Unit)": {
        "adversarial": 100,
        "technical": 100,
        "project": 100,
        "variation": 100,
        "decision": 100,
        "vague": 100,
        "partial": 97,
        "identity": 100,
        "metadata": 100,
        "temporal": 100,
    },
    "Latency": {
        "avg_ms": 3197,
        "min_ms": 38,
        "max_ms": 77932,
        "p50_ms": 500,  # estimated
    }
}

# Create figure with subplots
fig = plt.figure(figsize=(16, 12))
fig.suptitle("Context-Memory Skill: Complete Validation Summary", fontsize=16, fontweight='bold')

# 1. Cross-platform unit test comparison
ax1 = fig.add_subplot(2, 2, 1)
platforms = ['OpenClaw\n(4000 tests)', 'Claude Code\n(4457 tests)']
accuracies = [99.8, 99.98]
colors = ['#9C27B0', '#2196F3']
bars1 = ax1.bar(platforms, accuracies, color=colors)
ax1.set_ylabel('Accuracy (%)')
ax1.set_title('Unit Test Accuracy by Platform')
ax1.set_ylim(98, 100.5)
ax1.axhline(y=99, color='red', linestyle='--', alpha=0.5, label='99% threshold')
for bar, acc in zip(bars1, accuracies):
    ax1.annotate(f'{acc}%', xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
                 xytext=(0, 3), textcoords='offset points', ha='center', va='bottom', fontweight='bold')

# 2. Category breakdown heatmap style
ax2 = fig.add_subplot(2, 2, 2)
categories = list(data["Category Breakdown (Unit)"].keys())
cat_accuracies = list(data["Category Breakdown (Unit)"].values())
colors2 = ['#4CAF50' if a == 100 else '#FFC107' if a >= 95 else '#F44336' for a in cat_accuracies]
bars2 = ax2.barh(categories, cat_accuracies, color=colors2)
ax2.set_xlabel('Accuracy (%)')
ax2.set_title('Unit Test Accuracy by Category')
ax2.set_xlim(90, 102)
ax2.axvline(x=99, color='red', linestyle='--', alpha=0.5)
for bar, acc in zip(bars2, cat_accuracies):
    ax2.annotate(f'{acc}%', xy=(bar.get_width(), bar.get_y() + bar.get_height()/2),
                 xytext=(3, 0), textcoords='offset points', ha='left', va='center', fontsize=9)

# 3. Live validation summary
ax3 = fig.add_subplot(2, 2, 3)
live_labels = ['Found\n(66 queries)', 'Empty\n(5 queries)']
live_sizes = [66, 5]
live_colors = ['#4CAF50', '#9E9E9E']
ax3.pie(live_sizes, labels=live_labels, colors=live_colors, autopct='%1.1f%%', startangle=90,
        explode=(0.05, 0))
ax3.set_title('Live Session Validation (OpenClaw)\n71 queries, 93% retrieval rate')

# 4. Summary stats table
ax4 = fig.add_subplot(2, 2, 4)
ax4.axis('off')
table_data = [
    ['Metric', 'OpenClaw', 'Claude Code'],
    ['Unit Tests', '4,000', '4,457'],
    ['Unit Accuracy', '99.8%', '99.98%'],
    ['Live Queries', '71', '52'],
    ['Live Retrieval', '93%', '100%'],
    ['Avg Latency', '3,197ms', '349ms'],
    ['Min Latency', '38ms', '31ms'],
]
table = ax4.table(cellText=table_data, loc='center', cellLoc='center',
                  colWidths=[0.4, 0.3, 0.3])
table.auto_set_font_size(False)
table.set_fontsize(11)
table.scale(1.2, 1.8)

# Style header row
for i in range(3):
    table[(0, i)].set_facecolor('#333333')
    table[(0, i)].set_text_props(color='white', fontweight='bold')

# Style data rows
for i in range(1, len(table_data)):
    for j in range(3):
        if j == 0:
            table[(i, j)].set_facecolor('#f5f5f5')
        elif j == 1:
            table[(i, j)].set_facecolor('#E8D5F0')  # Light purple
        else:
            table[(i, j)].set_facecolor('#D5E8F0')  # Light blue

ax4.set_title('Complete Validation Summary', fontsize=12, fontweight='bold', pad=20)

plt.tight_layout()
plt.savefig('skills/context-memory/validation-results/complete-summary.png', dpi=150, bbox_inches='tight')
print("Saved complete-summary.png")

# Also create a simpler comparison chart for the blog
fig2, ax = plt.subplots(figsize=(10, 6))
x = np.arange(2)
width = 0.35

unit_tests = [4000, 4457]
unit_acc = [99.8, 99.98]

rects1 = ax.bar(x - width/2, unit_tests, width, label='Test Count', color='#9E9E9E', alpha=0.7)
ax2 = ax.twinx()
rects2 = ax2.bar(x + width/2, unit_acc, width, label='Accuracy %', color='#4CAF50')

ax.set_ylabel('Number of Tests')
ax2.set_ylabel('Accuracy (%)')
ax.set_title('Context-Memory Skill: Cross-Platform Validation\n(8,457 total tests)')
ax.set_xticks(x)
ax.set_xticklabels(['OpenClaw/Clawdbot', 'Claude Code'])
ax.legend(loc='upper left')
ax2.legend(loc='upper right')
ax2.set_ylim(98, 100.5)

for rect, count in zip(rects1, unit_tests):
    ax.annotate(f'{count:,}', xy=(rect.get_x() + rect.get_width()/2, rect.get_height()),
                xytext=(0, 3), textcoords='offset points', ha='center', fontsize=10)
for rect, acc in zip(rects2, unit_acc):
    ax2.annotate(f'{acc}%', xy=(rect.get_x() + rect.get_width()/2, rect.get_height()),
                 xytext=(0, 3), textcoords='offset points', ha='center', fontweight='bold')

plt.tight_layout()
plt.savefig('skills/context-memory/validation-results/cross-platform-summary.png', dpi=150)
print("Saved cross-platform-summary.png")
