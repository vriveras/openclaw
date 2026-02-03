#!/usr/bin/env python3
"""
Generate baseline comparison charts for blog post.
Shows improvement from baseline → skill on both platforms.
"""

import matplotlib.pyplot as plt
import numpy as np

# ============================================================
# DATA FROM VALIDATIONS
# ============================================================

# Clawdbot data (from 2000 test run)
clawdbot_data = {
    "No Memory (baseline)": 35.4,
    "Semantic Search": 82.9,
    "RLM Keywords (basic)": 88.2,
    "Hybrid (basic)": 89.8,
    "RLM Keywords (enhanced)": 99.6,
    "Hybrid (enhanced)": 99.8,
}

# Claude Code data (from baseline-comparison-extended.py)
# Extended tests with fuzzy/concept cases that show skill value
claude_code_data = {
    "Baseline (grep)": 83.3,
    "With Skill": 90.0,
}

# Category breakdown - Clawdbot before/after
clawdbot_categories = {
    "partial": (35, 97),      # before, after
    "temporal": (61, 100),
    "decision": (48, 100),
    "adversarial": (100, 100),
    "technical": (85, 100),
}

# Category breakdown - Claude Code (from extended tests)
claude_categories = {
    "partial": (100, 100),    # baseline, skill - both handle exact matches
    "fuzzy": (0, 75),         # typos - skill adds +75%!
    "compound": (100, 100),   # camelCase - both work after fix
    "adversarial": (100, 88), # skill has some false positives from concepts
    "concept": (67, 67),      # abbreviations - room for improvement
}

# ============================================================
# CHART 1: Platform Comparison (Side by Side)
# ============================================================

fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# Clawdbot
ax1 = axes[0]
labels = list(clawdbot_data.keys())
values = list(clawdbot_data.values())
colors = ['#ef4444', '#f97316', '#eab308', '#84cc16', '#22c55e', '#10b981']
bars = ax1.barh(labels, values, color=colors)
ax1.set_xlim(0, 105)
ax1.set_xlabel('Accuracy (%)', fontweight='bold')
ax1.set_title('Clawdbot: Baseline → Enhanced\n(4,000 tests)', fontsize=12, fontweight='bold')
ax1.axvline(x=90, color='gray', linestyle='--', alpha=0.5)
for bar, val in zip(bars, values):
    ax1.text(val + 1, bar.get_y() + bar.get_height()/2, f'{val:.1f}%', 
             va='center', fontsize=10, fontweight='bold')

# Claude Code
ax2 = axes[1]
labels2 = list(claude_code_data.keys())
values2 = list(claude_code_data.values())
colors2 = ['#ef4444', '#22c55e']
bars2 = ax2.barh(labels2, values2, color=colors2)
ax2.set_xlim(0, 105)
ax2.set_xlabel('Accuracy (%)', fontweight='bold')
ax2.set_title('Claude Code: Baseline → Skill\n(30 extended tests)', fontsize=12, fontweight='bold')
for bar, val in zip(bars2, values2):
    ax2.text(val + 1, bar.get_y() + bar.get_height()/2, f'{val:.1f}%', 
             va='center', fontsize=10, fontweight='bold')

plt.tight_layout()
plt.savefig('baseline-comparison-both.png', dpi=150, bbox_inches='tight', facecolor='white')
print("✅ Generated baseline-comparison-both.png")


# ============================================================
# CHART 2: Category Improvement (Before/After)
# ============================================================

fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# Clawdbot categories
ax1 = axes[0]
categories = list(clawdbot_categories.keys())
before = [clawdbot_categories[c][0] for c in categories]
after = [clawdbot_categories[c][1] for c in categories]

x = np.arange(len(categories))
width = 0.35

bars1 = ax1.bar(x - width/2, before, width, label='Before (basic)', color='#ef4444', alpha=0.8)
bars2 = ax1.bar(x + width/2, after, width, label='After (enhanced)', color='#22c55e', alpha=0.8)

ax1.set_ylabel('Accuracy (%)', fontweight='bold')
ax1.set_title('Clawdbot: Category Improvement', fontsize=12, fontweight='bold')
ax1.set_xticks(x)
ax1.set_xticklabels(categories, fontsize=10)
ax1.set_ylim(0, 110)
ax1.legend(loc='lower right')
ax1.axhline(y=90, color='gray', linestyle='--', alpha=0.5)

for bar in bars1:
    h = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2, h + 1, f'{h:.0f}%', ha='center', fontsize=9)
for bar in bars2:
    h = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2, h + 1, f'{h:.0f}%', ha='center', fontsize=9)

# Claude Code categories
ax2 = axes[1]
categories2 = list(claude_categories.keys())
baseline = [claude_categories[c][0] for c in categories2]
skill = [claude_categories[c][1] for c in categories2]

x2 = np.arange(len(categories2))
bars3 = ax2.bar(x2 - width/2, baseline, width, label='Baseline (grep)', color='#ef4444', alpha=0.8)
bars4 = ax2.bar(x2 + width/2, skill, width, label='With Skill', color='#22c55e', alpha=0.8)

ax2.set_ylabel('Accuracy (%)', fontweight='bold')
ax2.set_title('Claude Code: Category Improvement', fontsize=12, fontweight='bold')
ax2.set_xticks(x2)
ax2.set_xticklabels(categories2, fontsize=10)
ax2.set_ylim(0, 110)
ax2.legend(loc='lower right')

for bar in bars3:
    h = bar.get_height()
    ax2.text(bar.get_x() + bar.get_width()/2, h + 1, f'{h:.0f}%', ha='center', fontsize=9)
for bar in bars4:
    h = bar.get_height()
    ax2.text(bar.get_x() + bar.get_width()/2, h + 1, f'{h:.0f}%', ha='center', fontsize=9)

plt.tight_layout()
plt.savefig('category-improvement-both.png', dpi=150, bbox_inches='tight', facecolor='white')
print("✅ Generated category-improvement-both.png")


# ============================================================
# CHART 3: Journey Timeline (Clawdbot)
# ============================================================

fig, ax = plt.subplots(figsize=(12, 6))

stages = [
    'No Memory\n(baseline)',
    'Basic RLM\n(60 tests)',
    'Basic RLM\n(1K tests)',
    'Semantic\nSearch',
    'Hybrid\n(basic)',
    'Enhanced\nMatching',
    'Final\nHybrid'
]
values = [35.4, 95, 81, 82.9, 89.8, 99.6, 99.8]
colors = ['#ef4444', '#22c55e', '#f97316', '#3b82f6', '#8b5cf6', '#22c55e', '#10b981']

bars = ax.bar(stages, values, color=colors, edgecolor='black', linewidth=0.5)

ax.set_ylabel('Accuracy (%)', fontsize=12, fontweight='bold')
ax.set_title('The Journey: From 35% to 99.8%', fontsize=14, fontweight='bold')
ax.set_ylim(0, 110)
ax.axhline(y=90, color='gray', linestyle='--', alpha=0.5, label='90% threshold')

for bar, val in zip(bars, values):
    ax.text(bar.get_x() + bar.get_width()/2, val + 2, f'{val:.1f}%', 
            ha='center', fontsize=10, fontweight='bold')

# Add annotations
ax.annotate('Overconfidence!', xy=(1, 95), xytext=(1.5, 85),
            arrowprops=dict(arrowstyle='->', color='red'),
            fontsize=9, color='red')
ax.annotate('The Humbling', xy=(2, 81), xytext=(2.5, 70),
            arrowprops=dict(arrowstyle='->', color='orange'),
            fontsize=9, color='orange')

plt.tight_layout()
plt.savefig('journey-timeline.png', dpi=150, bbox_inches='tight', facecolor='white')
print("✅ Generated journey-timeline.png")


# ============================================================
# CHART 4: Combined Summary
# ============================================================

fig, ax = plt.subplots(figsize=(10, 6))

# Data - final validated numbers
platforms = ['Clawdbot\n(4K tests)', 'Claude Code\n(30 tests)']
baselines = [35.4, 83.3]
with_skill = [99.8, 90.0]
improvements = [64.4, 6.7]

x = np.arange(len(platforms))
width = 0.3

bars1 = ax.bar(x - width, baselines, width, label='Baseline', color='#ef4444', alpha=0.8)
bars2 = ax.bar(x, with_skill, width, label='With Skill', color='#22c55e', alpha=0.8)
bars3 = ax.bar(x + width, improvements, width, label='Improvement', color='#3b82f6', alpha=0.8)

ax.set_ylabel('Percentage (%)', fontsize=12, fontweight='bold')
ax.set_title('Cross-Platform Baseline Comparison', fontsize=14, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(platforms, fontsize=11)
ax.set_ylim(0, 110)
ax.legend(loc='upper right')

for bars in [bars1, bars2, bars3]:
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 2, f'{h:.1f}%', 
                ha='center', fontsize=9, fontweight='bold')

plt.tight_layout()
plt.savefig('cross-platform-baseline.png', dpi=150, bbox_inches='tight', facecolor='white')
print("✅ Generated cross-platform-baseline.png")

print("\n📊 All charts generated!")
