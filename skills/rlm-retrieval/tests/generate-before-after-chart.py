#!/usr/bin/env python3
"""Generate before/after enhanced matching comparison chart."""

import matplotlib.pyplot as plt
import numpy as np

# Data: Before enhanced matching vs After
categories = ['Overall\nHybrid', 'Overall\nRLM', 'Temporal', 'Partial', 'Decision', 'Variation']
before = [89.8, 88.2, 61, 35, 48, 73]
after = [99.8, 99.6, 100, 96, 100, 100]

# Calculate improvements
improvements = [a - b for a, b in zip(after, before)]

x = np.arange(len(categories))
width = 0.35

fig, ax = plt.subplots(figsize=(14, 8))

# Bars
bars1 = ax.bar(x - width/2, before, width, label='Before Enhanced Matching', color='#e74c3c', alpha=0.8)
bars2 = ax.bar(x + width/2, after, width, label='After Enhanced Matching', color='#2ecc71', alpha=0.8)

# Labels and styling
ax.set_ylabel('Accuracy (%)', fontsize=14)
ax.set_xlabel('Category', fontsize=14)
ax.set_title('Impact of Enhanced Matching\n(substring, compound, fuzzy, concepts)', fontsize=16, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(categories, fontsize=12)
ax.legend(fontsize=12, loc='lower right')
ax.set_ylim(0, 115)

# Add value labels on bars
for bar, val in zip(bars1, before):
    ax.annotate(f'{val}%',
                xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                xytext=(0, 3), textcoords="offset points",
                ha='center', va='bottom', fontsize=11, fontweight='bold', color='#c0392b')

for bar, val in zip(bars2, after):
    ax.annotate(f'{val}%',
                xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                xytext=(0, 3), textcoords="offset points",
                ha='center', va='bottom', fontsize=11, fontweight='bold', color='#27ae60')

# Add improvement arrows/annotations
for i, (b, a, imp) in enumerate(zip(before, after, improvements)):
    if imp > 0:
        ax.annotate(f'+{imp:.0f}%',
                    xy=(x[i] + width/2 + 0.05, (b + a) / 2),
                    fontsize=10, fontweight='bold', color='#2980b9',
                    ha='left')

# Reference line at 80%
ax.axhline(y=80, color='gray', linestyle='--', alpha=0.5, linewidth=1)
ax.text(len(categories) - 0.5, 81, '80% threshold', fontsize=9, color='gray', ha='right')

# Grid
ax.yaxis.grid(True, linestyle='--', alpha=0.3)
ax.set_axisbelow(True)

plt.tight_layout()

# Save
plt.savefig('enhanced-matching-impact.png', dpi=150, bbox_inches='tight', facecolor='white')
plt.savefig('enhanced-matching-impact.svg', bbox_inches='tight', facecolor='white')
print("✓ Saved enhanced-matching-impact.png and .svg")
