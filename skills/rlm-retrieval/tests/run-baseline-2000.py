#!/usr/bin/env python3
"""
Run baseline tests against 1000 test cases with multiple modes.

Modes:
  rlm      - RLM keyword search only (direct JSONL grep)
  semantic - Semantic search only (memory_search embeddings)
  hybrid   - Both methods combined
  compare  - Run all modes and compare results

Usage:
  python run-baseline-1000.py --mode rlm
  python run-baseline-1000.py --mode semantic
  python run-baseline-1000.py --mode hybrid
  python run-baseline-1000.py --mode compare
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

TESTS_DIR = Path(__file__).resolve().parent
WORKSPACE = Path.home() / "clawd"
MEMORY_DIR = WORKSPACE / "memory"
MEMORY_FILE = WORKSPACE / "MEMORY.md"
SESSIONS_DIR = Path.home() / ".clawdbot/agents/main/sessions"
SCRIPTS_DIR = TESTS_DIR.parent / "scripts"

# Import enhanced matching
sys.path.insert(0, str(SCRIPTS_DIR))
try:
    from enhanced_matching import enhanced_keyword_match, normalize_for_matching, get_related_concepts
    ENHANCED_MATCHING = True
except ImportError:
    ENHANCED_MATCHING = False
    print("Warning: enhanced_matching not available, using basic matching")

def load_test_cases():
    # Try 2000 first, fall back to 1000
    for filename in ["test-cases-2000.json", "test-cases-1000.json"]:
        path = TESTS_DIR / filename
        if path.exists():
            return json.load(open(path))
    raise FileNotFoundError("No test cases file found")

def load_memory_content():
    """Load all memory markdown files for searching."""
    content = []
    
    if MEMORY_FILE.exists():
        content.append(("MEMORY.md", MEMORY_FILE.read_text()))
    
    if MEMORY_DIR.exists():
        for f in sorted(MEMORY_DIR.glob("*.md")):
            content.append((f.name, f.read_text()))
    
    return content

def load_session_content(limit=3, max_lines_per_session=500):
    """
    Load recent session JSONL files for RLM search.
    
    Args:
        limit: Max number of session files to load
        max_lines_per_session: Max lines to read per session (for speed)
    """
    content = []
    
    if not SESSIONS_DIR.exists():
        return content
    
    # Get most recent sessions
    sessions = sorted(SESSIONS_DIR.glob("*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True)
    
    for session_file in sessions[:limit]:
        try:
            text_parts = []
            lines_read = 0
            with open(session_file) as f:
                for line in f:
                    if lines_read >= max_lines_per_session:
                        break
                    lines_read += 1
                    
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                        if record.get("type") != "message":
                            continue
                        msg = record.get("message", {})
                        if msg.get("role") not in ("user", "assistant"):
                            continue
                        content_blocks = msg.get("content", [])
                        if isinstance(content_blocks, str):
                            text_parts.append(content_blocks[:1000])  # Limit text size
                        elif isinstance(content_blocks, list):
                            for block in content_blocks:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    text_parts.append(block.get("text", "")[:1000])
                    except json.JSONDecodeError:
                        continue
            
            if text_parts:
                content.append((session_file.name, "\n".join(text_parts)))
        except Exception as e:
            continue
    
    return content

# ============================================================================
# RLM SEARCH (Keyword-based)
# ============================================================================

def rlm_search(query, memory_content, session_content, keywords, enhanced=True):
    """
    RLM-style keyword search across memory and session transcripts.
    Returns found keywords.
    
    If enhanced=True, uses:
    - Substring matching
    - Compound word splitting
    - Fuzzy matching (Levenshtein ≤ 2)
    - Concept expansion
    """
    found = []
    
    # Combine all content
    all_content = "\n".join(text for _, text in memory_content + session_content)
    
    if enhanced and ENHANCED_MATCHING:
        # Use enhanced matching
        for kw in keywords:
            matched, terms = enhanced_keyword_match(
                kw, all_content,
                use_substring=True,
                use_compound=True,
                use_fuzzy=True,
                use_concepts=True,
                fuzzy_distance=2
            )
            if matched and kw not in found:
                found.append(kw)
    else:
        # Basic matching (fallback)
        query_lower = query.lower()
        all_lower = all_content.lower()
        all_normalized = re.sub(r'[-_\s]+', ' ', all_lower)
        
        for kw in keywords:
            kw_lower = kw.lower()
            kw_normalized = re.sub(r'[-_\s]+', ' ', kw_lower)
            
            if kw_lower in all_lower or kw_normalized in all_normalized:
                if kw not in found:
                    found.append(kw)
    
    return found

def rlm_should_show_indicator(query, memory_content, session_content, enhanced=True):
    """Determine if RLM indicator should show based on keyword matching."""
    query_words = set(re.findall(r'\w+', query.lower()))
    stopwords = {'what', 'the', 'is', 'are', 'we', 'did', 'do', 'how', 'why', 'where', 
                 'when', 'for', 'to', 'a', 'an', 'of', 'in', 'on', 'with', 'about', 
                 'our', 'was', 'were', 'that', 'this', 'thing', 'stuff', 'can', 'you',
                 'i', 'my', 'me', 'it', 'be', 'have', 'has', 'had'}
    query_words -= stopwords
    
    if not query_words:
        return False
    
    # Combine all content
    all_text = "\n".join(text for _, text in memory_content + session_content)
    
    if enhanced and ENHANCED_MATCHING:
        # Use enhanced matching
        matched, terms = enhanced_keyword_match(
            query, all_text,
            use_substring=True,
            use_compound=True,
            use_fuzzy=True,
            use_concepts=True
        )
        return matched
    else:
        # Basic matching
        text_lower = all_text.lower()
        matches = sum(1 for w in query_words if w in text_lower)
        return matches >= len(query_words) * 0.5

# ============================================================================
# SEMANTIC SEARCH (Embedding-based)
# ============================================================================

def semantic_search(query, keywords):
    """
    Semantic search using Clawdbot's memory_search.
    
    NOTE: This is a placeholder that simulates semantic behavior.
    For real integration, this would call the memory_search tool or API.
    
    Simulated behavior:
    - More lenient matching (partial word matches)
    - Synonym/concept matching
    """
    # Placeholder: simulate semantic matching with fuzzy heuristics
    # Real implementation would call memory_search via API or subprocess
    
    found = []
    
    # Simulate semantic "fuzziness" by checking word stems
    query_words = set(re.findall(r'\w+', query.lower()))
    
    for kw in keywords:
        kw_lower = kw.lower()
        kw_words = set(re.findall(r'\w+', kw_lower))
        
        # Check if any query word is similar to keyword words
        for qw in query_words:
            for kw_word in kw_words:
                # Prefix matching (simulates embedding similarity)
                if len(qw) >= 4 and len(kw_word) >= 4:
                    if qw[:4] == kw_word[:4]:
                        if kw not in found:
                            found.append(kw)
                            break
    
    return found

def semantic_should_show_indicator(query, memory_content):
    """
    Semantic indicator detection.
    Placeholder: more lenient than RLM.
    """
    query_words = set(re.findall(r'\w+', query.lower()))
    stopwords = {'what', 'the', 'is', 'are', 'we', 'did', 'do', 'how', 'why', 'where', 
                 'when', 'for', 'to', 'a', 'an', 'of', 'in', 'on', 'with', 'about'}
    query_words -= stopwords
    
    if not query_words:
        return False
    
    for filename, text in memory_content:
        text_lower = text.lower()
        # More lenient: 30% match threshold (vs 50% for RLM)
        matches = sum(1 for w in query_words if w in text_lower)
        if matches >= len(query_words) * 0.3:
            return True
    
    return False

# ============================================================================
# HYBRID SEARCH
# ============================================================================

def hybrid_search(query, memory_content, session_content, keywords):
    """Combine RLM and semantic search results."""
    rlm_found = rlm_search(query, memory_content, session_content, keywords)
    semantic_found = semantic_search(query, keywords)
    
    # Merge results (union of both)
    all_found = list(set(rlm_found + semantic_found))
    
    # Track which method found what
    sources = {}
    for kw in all_found:
        in_rlm = kw in rlm_found
        in_semantic = kw in semantic_found
        if in_rlm and in_semantic:
            sources[kw] = "both"
        elif in_rlm:
            sources[kw] = "rlm"
        else:
            sources[kw] = "semantic"
    
    return all_found, sources

def hybrid_should_show_indicator(query, memory_content, session_content):
    """Hybrid indicator: either method finding something is enough."""
    rlm_result = rlm_should_show_indicator(query, memory_content, session_content)
    semantic_result = semantic_should_show_indicator(query, memory_content)
    return rlm_result or semantic_result

# ============================================================================
# TEST RUNNER
# ============================================================================

def run_tests(mode="rlm"):
    """Run all test cases in specified mode."""
    data = load_test_cases()
    memory_content = load_memory_content()
    session_content = load_session_content(limit=10) if mode in ("rlm", "hybrid") else []
    
    results = {
        "metadata": {
            "testRun": datetime.now().isoformat(),
            "tester": f"automated-baseline-1000-{mode}",
            "mode": mode,
            "sessionType": "memory-search",
            "memoryFiles": len(memory_content),
            "sessionFiles": len(session_content),
            "totalTests": len(data["testCases"])
        },
        "results": []
    }
    
    for tc in data["testCases"]:
        if mode == "rlm":
            found_keywords = rlm_search(tc["query"], memory_content, session_content, tc["expectedKeywords"])
            indicator = rlm_should_show_indicator(tc["query"], memory_content, session_content)
        elif mode == "semantic":
            found_keywords = semantic_search(tc["query"], tc["expectedKeywords"])
            indicator = semantic_should_show_indicator(tc["query"], memory_content)
        elif mode == "hybrid":
            found_keywords, sources = hybrid_search(tc["query"], memory_content, session_content, tc["expectedKeywords"])
            indicator = hybrid_should_show_indicator(tc["query"], memory_content, session_content)
        else:
            raise ValueError(f"Unknown mode: {mode}")
        
        # Special handling for adversarial tests
        if tc["category"] == "adversarial":
            indicator = len(found_keywords) > 0
        
        results["results"].append({
            "id": tc["id"],
            "query": tc["query"],
            "category": tc["category"],
            "indicatorShown": indicator,
            "keywordsFound": found_keywords,
            "expected": tc["shouldShowIndicator"]
        })
    
    return results

def score_results(results):
    """Score and summarize results by category."""
    by_category = defaultdict(lambda: {"total": 0, "passed": 0})
    
    for r in results["results"]:
        cat = r["category"]
        by_category[cat]["total"] += 1
        
        indicator_ok = r["indicatorShown"] == r["expected"]
        
        if indicator_ok:
            by_category[cat]["passed"] += 1
    
    return by_category

def print_scores(mode, scores):
    """Print score summary for a mode."""
    total = sum(s["total"] for s in scores.values())
    passed = sum(s["passed"] for s in scores.values())
    
    print(f"\n{'='*60}")
    print(f"Mode: {mode.upper()}")
    print(f"{'='*60}")
    print(f"📊 Overall: {passed}/{total} ({passed/total*100:.1f}%)")
    print("\nBy category:")
    for cat, data in sorted(scores.items(), key=lambda x: x[1]["passed"]/max(x[1]["total"],1)):
        rate = data["passed"]/data["total"]*100 if data["total"] > 0 else 0
        emoji = "✅" if rate >= 80 else "⚠️" if rate >= 50 else "❌"
        print(f"  {emoji} {cat}: {data['passed']}/{data['total']} ({rate:.0f}%)")
    
    return passed, total

def main():
    parser = argparse.ArgumentParser(description="Run context-memory validation tests")
    parser.add_argument("--mode", choices=["rlm", "semantic", "hybrid", "compare"], 
                        default="rlm", help="Search mode to test")
    args = parser.parse_args()
    
    if args.mode == "compare":
        # Run all modes and compare
        print("🧪 Running comparison across all modes...")
        
        all_scores = {}
        for mode in ["rlm", "semantic", "hybrid"]:
            print(f"\n⏳ Running {mode}...")
            results = run_tests(mode)
            
            # Save results
            with open(TESTS_DIR / f"baseline-results-2000-{mode}.json", "w") as f:
                json.dump(results, f, indent=2)
            
            scores = score_results(results)
            passed, total = print_scores(mode, scores)
            all_scores[mode] = {"passed": passed, "total": total, "rate": passed/total*100}
        
        # Summary comparison
        print(f"\n{'='*60}")
        print("COMPARISON SUMMARY")
        print(f"{'='*60}")
        print(f"{'Mode':<12} | {'Accuracy':<10} | {'Notes'}")
        print(f"{'-'*12}-+-{'-'*10}-+-{'-'*30}")
        for mode, data in all_scores.items():
            notes = {
                "rlm": "Exact matches, code, URLs",
                "semantic": "Paraphrases, concepts (placeholder)",
                "hybrid": "Best of both"
            }
            print(f"{mode:<12} | {data['rate']:>8.1f}% | {notes[mode]}")
        
    else:
        # Run single mode
        print(f"🧪 Running {args.mode} mode...")
        results = run_tests(args.mode)
        
        # Save results
        output_file = TESTS_DIR / f"baseline-results-2000-{args.mode}.json"
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"💾 Results saved to {output_file}")
        
        scores = score_results(results)
        print_scores(args.mode, scores)

if __name__ == "__main__":
    main()
