#!/usr/bin/env python3
"""
Compaction vs RLM Analysis

Compares three context management strategies:
A) Raw transcripts (RLM approach)
B) Summarized/compacted transcripts
C) Token efficiency analysis

Usage:
  python compaction-analysis.py --all
  python compaction-analysis.py --summarize
  python compaction-analysis.py --survival
  python compaction-analysis.py --tokens
"""

import json
import os
import sys
from pathlib import Path
from collections import defaultdict
import re

# Approximate tokens (1 token ≈ 4 chars)
def count_tokens(text):
    return len(text) // 4

def load_transcripts(sessions_dir, limit=20):
    """Load transcript text from JSONL files."""
    transcripts = []
    sessions_path = Path(sessions_dir)
    
    if not sessions_path.exists():
        print(f"Sessions dir not found: {sessions_dir}")
        return []
    
    files = sorted(sessions_path.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)[:limit]
    
    for f in files:
        try:
            messages = []
            with open(f) as fp:
                for line in fp:
                    try:
                        obj = json.loads(line)
                        if obj.get("type") == "message":
                            content = obj.get("message", {}).get("content", [])
                            for c in content:
                                if c.get("type") == "text":
                                    messages.append(c.get("text", ""))
                    except:
                        pass
            
            text = "\n".join(messages)
            if text.strip():
                transcripts.append({
                    "file": f.name,
                    "text": text,
                    "tokens": count_tokens(text),
                    "chars": len(text)
                })
        except Exception as e:
            print(f"Error loading {f}: {e}")
    
    return transcripts

def extract_facts(text):
    """Extract different types of facts from text."""
    facts = {
        "decisions": [],
        "technical": [],
        "names": [],
        "dates": [],
        "code": [],
        "paths": [],
        "urls": []
    }
    
    # Decisions (phrases like "decided", "chose", "will use", "approach")
    decision_patterns = [
        r"(?:decided|chose|picked|selected|went with|will use|using|approach)[^.]*\.",
        r"(?:the plan is|we'll|let's go with)[^.]*\."
    ]
    for p in decision_patterns:
        facts["decisions"].extend(re.findall(p, text, re.I))
    
    # Technical details (paths, commands, config)
    facts["paths"] = re.findall(r'[~/][a-zA-Z0-9_\-/\.]+', text)
    facts["urls"] = re.findall(r'https?://[^\s<>"]+', text)
    
    # Names (capitalized words that look like names)
    facts["names"] = list(set(re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b', text)))
    
    # Dates
    facts["dates"] = re.findall(r'\b\d{4}-\d{2}-\d{2}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}\b', text)
    
    # Code blocks
    code_blocks = re.findall(r'```[\s\S]*?```', text)
    facts["code"] = code_blocks[:10]  # Limit
    
    # Technical terms
    facts["technical"] = list(set(re.findall(r'\b(?:API|CLI|JSON|JSONL|RLM|WSL|SSH|HTTP|DNS|CNI|WAM|SSO)\b', text, re.I)))
    
    return facts

def simulate_compaction(text, ratio=0.2):
    """Simulate compaction by extracting key sentences."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    # Score sentences by importance indicators
    scored = []
    for s in sentences:
        score = 0
        # Decision indicators
        if re.search(r'\b(decided|chose|will|should|must|plan|approach)\b', s, re.I):
            score += 3
        # Technical content
        if re.search(r'[~/]|https?://|```', s):
            score += 2
        # Names/entities
        if re.search(r'\b[A-Z][a-z]+\b', s):
            score += 1
        # Length bonus (longer = more info)
        score += min(len(s) / 100, 2)
        scored.append((score, s))
    
    # Keep top sentences up to ratio
    scored.sort(reverse=True)
    target_chars = int(len(text) * ratio)
    
    kept = []
    total = 0
    for score, s in scored:
        if total + len(s) <= target_chars:
            kept.append(s)
            total += len(s)
    
    return " ".join(kept)

def analyze_survival(original_facts, compacted_facts):
    """Analyze what survives compaction."""
    survival = {}
    
    for fact_type in original_facts:
        orig = set(str(x)[:100] for x in original_facts[fact_type])
        comp = set(str(x)[:100] for x in compacted_facts[fact_type])
        
        if orig:
            survived = len(orig & comp)
            survival[fact_type] = {
                "original": len(orig),
                "survived": survived,
                "rate": survived / len(orig) * 100 if orig else 0
            }
    
    return survival

def run_analysis(sessions_dir):
    """Run full compaction vs RLM analysis."""
    print("=" * 60)
    print("COMPACTION vs RLM ANALYSIS")
    print("=" * 60)
    
    # Load transcripts
    print("\n📂 Loading transcripts...")
    transcripts = load_transcripts(sessions_dir, limit=20)
    
    if not transcripts:
        print("No transcripts found!")
        return
    
    total_tokens = sum(t["tokens"] for t in transcripts)
    total_chars = sum(t["chars"] for t in transcripts)
    
    print(f"   Loaded {len(transcripts)} sessions")
    print(f"   Total: {total_chars:,} chars / ~{total_tokens:,} tokens")
    
    # ========== A) SUMMARIZATION TEST ==========
    print("\n" + "=" * 60)
    print("A) SUMMARIZATION TEST (20% compression)")
    print("=" * 60)
    
    all_original_facts = defaultdict(list)
    all_compacted_facts = defaultdict(list)
    
    for t in transcripts:
        original_facts = extract_facts(t["text"])
        compacted_text = simulate_compaction(t["text"], ratio=0.2)
        compacted_facts = extract_facts(compacted_text)
        
        for k, v in original_facts.items():
            all_original_facts[k].extend(v)
        for k, v in compacted_facts.items():
            all_compacted_facts[k].extend(v)
    
    # ========== B) SURVIVAL ANALYSIS ==========
    print("\n" + "=" * 60)
    print("B) INFORMATION SURVIVAL BY TYPE")
    print("=" * 60)
    
    survival = analyze_survival(all_original_facts, all_compacted_facts)
    
    print(f"\n{'Type':<15} {'Original':<10} {'Survived':<10} {'Rate':<10}")
    print("-" * 45)
    
    for fact_type, data in sorted(survival.items(), key=lambda x: x[1]["rate"]):
        emoji = "✅" if data["rate"] >= 70 else "⚠️" if data["rate"] >= 40 else "❌"
        print(f"{fact_type:<15} {data['original']:<10} {data['survived']:<10} {emoji} {data['rate']:.0f}%")
    
    avg_survival = sum(d["rate"] for d in survival.values()) / len(survival) if survival else 0
    print(f"\n{'AVERAGE':<15} {'':<10} {'':<10} {avg_survival:.0f}%")
    
    # ========== C) TOKEN EFFICIENCY ==========
    print("\n" + "=" * 60)
    print("C) TOKEN EFFICIENCY ANALYSIS")
    print("=" * 60)
    
    total_facts = sum(len(v) for v in all_original_facts.values())
    compacted_tokens = int(total_tokens * 0.2)
    
    print(f"\n📊 Raw Transcripts (RLM approach):")
    print(f"   Tokens: {total_tokens:,}")
    print(f"   Facts extractable: {total_facts}")
    print(f"   Tokens per fact: {total_tokens / total_facts:.1f}" if total_facts else "   N/A")
    
    survived_facts = sum(d["survived"] for d in survival.values())
    print(f"\n📊 Compacted (20% size):")
    print(f"   Tokens: {compacted_tokens:,}")
    print(f"   Facts surviving: {survived_facts}")
    print(f"   Tokens per fact: {compacted_tokens / survived_facts:.1f}" if survived_facts else "   N/A")
    
    # Context budget scenarios
    print("\n📊 Context Budget Scenarios (50k token limit):")
    budget = 50000
    
    # RLM: search retrieves ~5k tokens of relevant context
    rlm_retrieved = 5000
    rlm_facts_accessible = total_facts  # Can search all
    
    # Compacted: fit more sessions but lose detail
    sessions_in_budget_compacted = budget // (compacted_tokens // len(transcripts)) if transcripts else 0
    compacted_facts_accessible = int(survived_facts * min(sessions_in_budget_compacted / len(transcripts), 1))
    
    print(f"\n   RLM (search-based):")
    print(f"   - Tokens used per query: ~{rlm_retrieved:,}")
    print(f"   - Facts accessible: {total_facts} (100% via search)")
    
    print(f"\n   Compacted (in-context):")
    print(f"   - Sessions fitting: ~{sessions_in_budget_compacted}")
    print(f"   - Facts accessible: ~{compacted_facts_accessible} ({compacted_facts_accessible/total_facts*100:.0f}% of original)")
    
    # ========== SUMMARY ==========
    print("\n" + "=" * 60)
    print("SUMMARY: COMPACTION vs RLM")
    print("=" * 60)
    
    print("""
┌─────────────────┬──────────────────┬──────────────────┐
│ Metric          │ Compaction       │ RLM (Raw Search) │
├─────────────────┼──────────────────┼──────────────────┤
│ Token usage     │ 20% of original  │ ~5-10k per query │
│ Fact survival   │ {avg:.0f}% average     │ 100%             │
│ Code blocks     │ {code}            │ ✅ Full          │
│ Paths/URLs      │ {paths}            │ ✅ Full          │
│ Decisions       │ {dec}            │ ✅ Full          │
│ Technical terms │ {tech}            │ ✅ Full          │
│ Query latency   │ Instant          │ Search required  │
│ Cross-session   │ ❌ Limited       │ ✅ All sessions  │
└─────────────────┴──────────────────┴──────────────────┘
""".format(
        avg=avg_survival,
        code="✅ Good" if survival.get("code", {}).get("rate", 0) >= 70 else "⚠️ Partial" if survival.get("code", {}).get("rate", 0) >= 40 else "❌ Poor",
        paths="✅ Good" if survival.get("paths", {}).get("rate", 0) >= 70 else "⚠️ Partial" if survival.get("paths", {}).get("rate", 0) >= 40 else "❌ Poor",
        dec="✅ Good" if survival.get("decisions", {}).get("rate", 0) >= 70 else "⚠️ Partial" if survival.get("decisions", {}).get("rate", 0) >= 40 else "❌ Poor",
        tech="✅ Good" if survival.get("technical", {}).get("rate", 0) >= 70 else "⚠️ Partial" if survival.get("technical", {}).get("rate", 0) >= 40 else "❌ Poor"
    ))
    
    return {
        "total_tokens": total_tokens,
        "total_facts": total_facts,
        "survival": survival,
        "avg_survival": avg_survival
    }

if __name__ == "__main__":
    sessions_dir = Path.home() / ".clawdbot/agents/main/sessions"
    results = run_analysis(sessions_dir)
