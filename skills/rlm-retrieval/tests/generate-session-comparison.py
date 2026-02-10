#!/usr/bin/env python3
"""
Generate comparison chart: Main Session vs Sub-Agent Session retrieval capabilities
"""

import matplotlib.pyplot as plt
import numpy as np

# Data from our validation tests
categories = ['Fact\nRetrieval', 'Partial\nMatching', 'Temporal\nFiltering', 'Adversarial\nRejection']

# Main session with memory_search (semantic embeddings)
main_session_semantic = [60, 75, 33, 100]

# Sub-agent with RLM skill only (no memory_search access)
subagent_skill = [75, 87.5, 100, 100]

# Hybrid (main session with both)
hybrid = [80, 87.5, 100, 100]

x = np.arange(len(categories))
width = 0.25

fig, ax = plt.subplots(figsize=(12, 7))

# Create bars
bars1 = ax.bar(x - width, main_session_semantic, width, label='Main Session\n(Semantic Only)', color='#6366f1', alpha=0.8)
bars2 = ax.bar(x, subagent_skill, width, label='Sub-Agent\n(RLM Skill)', color='#22c55e', alpha=0.8)
bars3 = ax.bar(x + width, hybrid, width, label='Hybrid\n(Both)', color='#f59e0b', alpha=0.8)

# Customize
ax.set_ylabel('Accuracy (%)', fontsize=12, fontweight='bold')
ax.set_title('Retrieval Accuracy: Main Session vs Sub-Agent vs Hybrid', fontsize=14, fontweight='bold', pad=20)
ax.set_xticks(x)
ax.set_xticklabels(categories, fontsize=11)
ax.set_ylim(0, 110)
ax.legend(loc='upper left', fontsize=10)
ax.grid(axis='y', alpha=0.3)

# Add value labels on bars
def add_labels(bars):
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:.0f}%',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=9, fontweight='bold')

add_labels(bars1)
add_labels(bars2)
add_labels(bars3)

# Add annotation
ax.text(0.02, 0.98, 'Key: Sub-agents lack memory_search but can use RLM skill\nHybrid approach gives best overall results', 
        transform=ax.transAxes, fontsize=9, verticalalignment='top',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

plt.tight_layout()
plt.savefig('session-comparison.png', dpi=150, bbox_inches='tight', facecolor='white')
plt.savefig('session-comparison.svg', bbox_inches='tight', facecolor='white')
print("✅ Generated session-comparison.png and .svg")
