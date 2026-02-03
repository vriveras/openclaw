#!/usr/bin/env python3
"""
Extended baseline comparison with synthetic edge cases.
Shows where the skill helps vs baseline grep.

Usage:
    python baseline-comparison-extended.py
"""

import json
import sys
from pathlib import Path

SCRIPT_DIR = (Path(__file__).parent / ".." / "scripts").resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from enhanced_matching import enhanced_keyword_match

# Simulated content representing typical Claude Code sessions
# Based on real session patterns but with specific test patterns
SIMULATED_CONTENT = """
## Chess Game Implementation

Building a real-time chess game with WebSocket communication.
The server handles move validation using chess.js library.

Key features:
- Real-time move updates via WebSocket  
- Server-side checkmate detection
- Glicko-2 rating system integration
- PostgreSQL database for game history

### Move Validation Logic

The validateMove() function checks:
1. Source and target squares
2. Piece movement rules
3. Check/checkmate conditions
4. En passant and castling

### Container Deployment

Using WLXC (Windows Linux Container eXecution) for:
- Process isolation
- Policy-based permissions
- Windows interop

### Context Memory Testing

Testing the context-memory skill with:
- update-state.py for state management
- temporal_parser.py for date handling
- search.py for retrieval

Files tested:
- init.py
- save.py
- resume.py

### Configuration

TypeScript configuration in tsconfig.json
React components in src/components/
JavaScript modules in lib/

### API Endpoints

REST API endpoints:
- POST /api/game/create
- GET /api/game/:id
- PUT /api/game/:id/move

OAuth2 authentication flow with JWT tokens.

### Database Schema

PostgreSQL tables:
- games (id, white_id, black_id, fen, created_at)
- moves (id, game_id, from_sq, to_sq, piece)
- users (id, email, rating)
"""


def baseline_match(query: str, content: str) -> bool:
    """Baseline: simple grep/contains (case-insensitive)."""
    query_lower = query.lower()
    content_lower = content.lower()
    words = query_lower.split()
    return all(word in content_lower for word in words)


def run_comparison():
    """Run comparison tests."""
    
    tests = [
        # === PARTIAL MATCHING (skill helps) ===
        ("Glicko", True, "partial"),           # Should match "Glicko-2"
        ("validate", True, "partial"),         # Should match "validateMove"
        ("Web", True, "partial"),              # Should match "WebSocket"
        ("check", True, "partial"),            # Should match "checkmate"
        ("config", True, "partial"),           # Should match "tsconfig"
        
        # === COMPOUND SPLITTING (skill helps) ===
        ("WebSocket", True, "compound"),       # Already works
        ("PostgreSQL", True, "compound"),      # Already works
        ("tsconfig", True, "compound"),        # ts + config
        ("validateMove", True, "compound"),    # validate + move
        ("from_sq", True, "compound"),         # from_sq
        
        # === FUZZY MATCHING (skill helps) ===
        ("postgress", True, "fuzzy"),          # Typo for PostgreSQL
        ("websockt", True, "fuzzy"),           # Typo for WebSocket
        ("javascrpt", True, "fuzzy"),          # Typo for JavaScript
        ("chessgame", True, "fuzzy"),          # chess game merged
        
        # === CONCEPT EXPANSION (skill helps) ===
        ("auth", True, "concept"),             # Should match OAuth2
        ("db", True, "concept"),               # Should match database
        ("rating", True, "concept"),           # Should match Glicko-2
        
        # === ADVERSARIAL (both should reject) ===
        ("MongoDB replication", False, "adversarial"),
        ("Kubernetes pods", False, "adversarial"),
        ("Elasticsearch Kibana", False, "adversarial"),
        ("GraphQL Apollo", False, "adversarial"),
        ("terraform ansible", False, "adversarial"),
        ("cryptocurrency blockchain", False, "adversarial"),
        ("machine learning neural", False, "adversarial"),
        ("flutter dart mobile", False, "adversarial"),
        
        # === FACT RETRIEVAL (both work) ===
        ("chess game", True, "fact"),
        ("move validation", True, "fact"),
        ("context memory", True, "fact"),
        ("REST API", True, "fact"),
        ("database schema", True, "fact"),
    ]
    
    baseline = {"passed": 0, "total": 0, "by_cat": {}}
    skill = {"passed": 0, "total": 0, "by_cat": {}}
    
    print("=" * 70)
    print("EXTENDED BASELINE COMPARISON")
    print("=" * 70)
    print()
    
    for query, expected, category in tests:
        baseline["total"] += 1
        skill["total"] += 1
        
        for results in [baseline, skill]:
            if category not in results["by_cat"]:
                results["by_cat"][category] = {"passed": 0, "total": 0, "tests": []}
            results["by_cat"][category]["total"] += 1
        
        # Baseline
        b_match = baseline_match(query, SIMULATED_CONTENT)
        b_correct = (b_match == expected)
        if b_correct:
            baseline["passed"] += 1
            baseline["by_cat"][category]["passed"] += 1
        baseline["by_cat"][category]["tests"].append((query, expected, b_match, b_correct))
        
        # Skill
        s_match, terms = enhanced_keyword_match(query, SIMULATED_CONTENT)
        s_correct = (s_match == expected)
        if s_correct:
            skill["passed"] += 1
            skill["by_cat"][category]["passed"] += 1
        skill["by_cat"][category]["tests"].append((query, expected, s_match, s_correct, terms))
    
    # Results
    b_acc = baseline["passed"] / baseline["total"] * 100
    s_acc = skill["passed"] / skill["total"] * 100
    improvement = s_acc - b_acc
    
    print(f"Total tests:     {baseline['total']}")
    print()
    print(f"📊 BASELINE (grep): {b_acc:.1f}%")
    print(f"📊 WITH SKILL:      {s_acc:.1f}%")
    print(f"📈 IMPROVEMENT:     +{improvement:.1f}%")
    print()
    
    print("| Category | Baseline | Skill | Δ |")
    print("|----------|----------|-------|---|")
    for cat in ["partial", "compound", "fuzzy", "concept", "adversarial", "fact"]:
        if cat in baseline["by_cat"]:
            b = baseline["by_cat"][cat]
            s = skill["by_cat"][cat]
            b_pct = b["passed"] / b["total"] * 100 if b["total"] else 0
            s_pct = s["passed"] / s["total"] * 100 if s["total"] else 0
            delta = s_pct - b_pct
            d_str = f"+{delta:.0f}%" if delta >= 0 else f"{delta:.0f}%"
            print(f"| {cat:12} | {b_pct:5.0f}% | {s_pct:4.0f}% | {d_str} |")
    
    # Show failures
    print()
    print("FAILURES:")
    for cat in baseline["by_cat"]:
        for test in baseline["by_cat"][cat]["tests"]:
            q, exp, got, correct = test[:4]
            if not correct:
                print(f"  [baseline] [{cat}] '{q}': expected {exp}, got {got}")
        for test in skill["by_cat"][cat]["tests"]:
            q, exp, got, correct = test[:4]
            terms = test[4] if len(test) > 4 else []
            if not correct:
                print(f"  [skill] [{cat}] '{q}': expected {exp}, got {got}")
                if terms:
                    print(f"           terms: {terms[:3]}")
    
    print()
    print("=" * 70)
    print("NUMBERS FOR generate-baseline-charts.py:")
    print("=" * 70)
    print()
    print("# Claude Code data (from extended tests)")
    print("claude_code_data = {")
    print(f'    "Baseline (grep)": {b_acc:.1f},')
    print(f'    "With Skill": {s_acc:.1f},')
    print("}")
    print()
    print("# Claude categories")
    print("claude_categories = {")
    for cat in ["partial", "fuzzy", "compound", "adversarial"]:
        if cat in baseline["by_cat"]:
            b = baseline["by_cat"][cat]
            s = skill["by_cat"][cat]
            b_pct = int(b["passed"] / b["total"] * 100) if b["total"] else 0
            s_pct = int(s["passed"] / s["total"] * 100) if s["total"] else 0
            print(f'    "{cat}": ({b_pct}, {s_pct}),')
    print("}")
    
    return 0


if __name__ == "__main__":
    sys.exit(run_comparison())
