#!/usr/bin/env python3
"""
Enhanced Matching for Context Memory

Provides improved partial matching capabilities:
1. Substring matching — query word IN content word
2. Case-normalized compound — split camelCase, kebab-case, snake_case
3. Fuzzy matching — Levenshtein distance ≤ 2
4. Concept index — related terms mapping

Cross-platform, no external dependencies.
"""

import re
from typing import List, Set, Dict, Optional, Tuple

# ============================================================================
# CONCEPT INDEX - Related terms mapping
# ============================================================================

CONCEPT_INDEX = {
    # Rating systems
    "glicko": ["rating", "elo", "chess", "leaderboard", "rank", "score"],
    "elo": ["rating", "glicko", "chess", "rank", "score"],
    
    # Projects
    "chessrt": ["chess", "rating", "game", "glicko", "leaderboard"],
    "wlxc": ["container", "windows", "linux", "containerd", "runtime"],
    "clawdbot": ["agent", "bot", "assistant", "gateway", "channel"],
    "context-memory": ["rlm", "memory", "retrieval", "search", "transcript"],
    
    # Technical
    "rlm": ["memory", "retrieval", "search", "context", "transcript"],
    "jsonl": ["json", "log", "transcript", "session", "file"],
    "wsl": ["windows", "linux", "subsystem", "ubuntu"],
    "oauth": ["auth", "authentication", "token", "login", "security"],
    "jwt": ["token", "auth", "authentication", "bearer"],
    
    # Platforms
    "whatsapp": ["message", "chat", "channel", "phone"],
    "telegram": ["message", "chat", "channel", "bot"],
    "discord": ["message", "chat", "channel", "server", "guild"],
    "slack": ["message", "chat", "channel", "workspace"],
    
    # File types
    "typescript": ["ts", "javascript", "node", "code"],
    "python": ["py", "script", "code"],
    "markdown": ["md", "readme", "docs", "documentation"],
    
    # DevOps / Infrastructure
    "k8s": ["kubernetes", "container", "pod", "deployment", "cluster"],
    "kubernetes": ["k8s", "container", "pod", "deployment", "cluster"],
    "docker": ["container", "image", "dockerfile", "compose"],
    "ci/cd": ["pipeline", "deploy", "build", "github", "actions"],
    "cicd": ["pipeline", "deploy", "build", "github", "actions"],
    
    # Security
    "ssl": ["tls", "https", "certificate", "encryption", "secure"],
    "tls": ["ssl", "https", "certificate", "encryption", "secure"],
    
    # Testing
    "e2e": ["end-to-end", "playwright", "cypress", "test", "browser"],
    "unit": ["test", "jest", "pytest", "mock"],
    
    # Frontend
    "css": ["style", "stylesheet", "tailwind", "sass", "scss"],
    "react": ["component", "jsx", "tsx", "hooks", "state"],
}

def get_related_concepts(term: str) -> List[str]:
    """Get related terms for a concept."""
    term_lower = term.lower()
    
    # Direct lookup
    if term_lower in CONCEPT_INDEX:
        return CONCEPT_INDEX[term_lower]
    
    # Check if term appears in any concept's related terms
    related = []
    for concept, terms in CONCEPT_INDEX.items():
        if term_lower in terms:
            related.append(concept)
            related.extend(t for t in terms if t != term_lower)
    
    return list(set(related))[:5]  # Limit to 5 related terms

# ============================================================================
# COMPOUND WORD SPLITTING
# ============================================================================

def split_compound(word: str) -> List[str]:
    """
    Split compound words into parts.
    
    Handles:
    - camelCase → camel, case
    - PascalCase → pascal, case
    - kebab-case → kebab, case
    - snake_case → snake, case
    - SCREAMING_SNAKE → screaming, snake
    """
    parts = []
    
    # First split on - and _
    tokens = re.split(r'[-_]', word)
    
    for token in tokens:
        if not token:
            continue
            
        # Split camelCase and PascalCase
        # Insert space before uppercase letters that follow lowercase
        split = re.sub(r'([a-z])([A-Z])', r'\1 \2', token)
        # Insert space before uppercase letters followed by lowercase (for acronyms)
        split = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', split)
        
        parts.extend(split.lower().split())
    
    return parts

def normalize_for_matching(text: str) -> Set[str]:
    """
    Normalize text for matching by extracting all word variants.
    
    Returns set of lowercase words including compound splits.
    """
    words = set()
    
    # Extract raw words
    raw_words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_-]*\b', text)
    
    for word in raw_words:
        word_lower = word.lower()
        words.add(word_lower)
        
        # Add compound splits
        parts = split_compound(word)
        words.update(parts)
    
    return words

# ============================================================================
# LEVENSHTEIN DISTANCE (Fuzzy matching)
# ============================================================================

def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate Levenshtein edit distance between two strings.
    
    Pure Python implementation, no dependencies.
    """
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    
    if len(s2) == 0:
        return len(s1)
    
    prev_row = range(len(s2) + 1)
    
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost is 0 if characters match, 1 otherwise
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    
    return prev_row[-1]

def fuzzy_match(query_word: str, content_word: str, max_distance: int = 2) -> bool:
    """
    Check if two words match within Levenshtein distance.
    
    Conservative thresholds:
    - Requires same first 2 characters (prevents pods≈post, dart≈date)
    - 4-6 char words: max distance 1
    - 7+ char words: max distance 2
    - Words < 4 chars: no fuzzy matching
    """
    q = query_word.lower()
    c = content_word.lower()
    
    # Exact match
    if q == c:
        return True
    
    # Only fuzzy match longer words
    if len(q) < 4 or len(c) < 4:
        return False
    
    # Require same prefix (first 2 chars) to reduce false positives
    if q[:2] != c[:2]:
        return False
    
    # Tighter distance for shorter words
    effective_max = 1 if len(q) <= 6 else min(2, max_distance)
    
    # Skip if lengths differ too much
    if abs(len(q) - len(c)) > effective_max:
        return False
    
    return levenshtein_distance(q, c) <= effective_max

# ============================================================================
# SUBSTRING MATCHING
# ============================================================================

def substring_match(query_word: str, content_word: str, min_length: int = 3) -> bool:
    """
    Check if query word is a substring of content word.
    
    Only matches if:
    - Query word is at least min_length characters
    - Query word is found in content word
    - Does NOT match if content word is in query word (prevents "and" matching "cassandra")
    """
    q = query_word.lower()
    c = content_word.lower()
    
    if len(q) < min_length:
        return False
    
    # Only match if query is substring of content, not vice versa
    return q in c

# ============================================================================
# ENHANCED SEARCH
# ============================================================================

def enhanced_keyword_match(
    query: str, 
    content: str,
    use_substring: bool = True,
    use_compound: bool = True,
    use_fuzzy: bool = True,
    use_concepts: bool = True,
    fuzzy_distance: int = 2,
    max_content_words: int = 5000  # Limit for performance
) -> Tuple[bool, List[str]]:
    """
    Enhanced keyword matching with all improvements.
    
    Returns: (matched: bool, matched_terms: List[str])
    """
    # Normalize content (with limit for performance)
    if use_compound:
        content_words = normalize_for_matching(content[:100000])  # Limit content size
    else:
        content_words = set(re.findall(r'\b[a-zA-Z][a-zA-Z0-9_-]*\b', content[:100000].lower()))
    
    # Limit content words for fuzzy matching performance
    content_words_list = list(content_words)[:max_content_words]
    content_words = set(content_words_list)
    
    # Extract query words - preserve case for compound splitting first
    query_words_raw = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_-]*\b', query)
    
    # Expand query with compound splits (preserves camelCase detection)
    expanded_query = set()
    if use_compound:
        for word in query_words_raw:
            # split_compound handles case detection and returns lowercase
            expanded_query.update(split_compound(word))
    else:
        expanded_query = set(w.lower() for w in query_words_raw)
    
    # Add lowercase originals
    expanded_query.update(w.lower() for w in query_words_raw)
    
    # Expand query with concepts
    if use_concepts:
        for word in list(expanded_query):
            related = get_related_concepts(word)
            expanded_query.update(related)
    
    matched_terms = []
    
    for qword in expanded_query:
        if len(qword) < 2:
            continue
            
        # 1. Exact match (fast)
        if qword in content_words:
            matched_terms.append(qword)
            continue
        
        # 2. Substring match (medium speed)
        if use_substring:
            for cword in content_words_list[:2000]:  # Limit for performance
                if substring_match(qword, cword):
                    matched_terms.append(f"{qword}⊂{cword}")
                    break
            else:
                # 3. Fuzzy match (slow, only if substring didn't match)
                if use_fuzzy:
                    for cword in content_words_list[:1000]:  # More limited for fuzzy
                        if fuzzy_match(qword, cword, fuzzy_distance):
                            matched_terms.append(f"{qword}≈{cword}")
                            break
    
    return len(matched_terms) > 0, matched_terms

def enhanced_search_memory(
    query: str, 
    memory_content: List[Tuple[str, str]], 
    keywords: List[str],
    **kwargs
) -> List[str]:
    """
    Search memory with enhanced matching.
    
    Args:
        query: Search query
        memory_content: List of (filename, content) tuples
        keywords: Expected keywords to find
        **kwargs: Options passed to enhanced_keyword_match
    
    Returns: List of found keywords
    """
    found = []
    
    # Combine all content
    all_content = "\n".join(content for _, content in memory_content)
    
    for kw in keywords:
        matched, terms = enhanced_keyword_match(kw, all_content, **kwargs)
        if matched:
            found.append(kw)
    
    return found

# ============================================================================
# CLI for testing
# ============================================================================

if __name__ == "__main__":
    import sys
    
    # Test cases
    tests = [
        ("Glicko", "We use Glicko-2 rating system for ChessRT leaderboard"),
        ("ReadMessage", "The ReadMessageItem function handles email retrieval"),
        ("context", "The context-memory skill provides retrieval"),
        ("postgres", "We use PostgreSQL for the database"),  # Fuzzy
        ("auth", "OAuth2 authentication flow with JWT tokens"),  # Concept
        ("App", "Check the AppData folder"),  # Substring
        ("HostWindows", "The HostWindowsContainer function"),  # Compound
    ]
    
    print("Enhanced Matching Tests\n")
    print("=" * 60)
    
    for query, content in tests:
        matched, terms = enhanced_keyword_match(query, content)
        status = "✅" if matched else "❌"
        print(f"\n{status} Query: '{query}'")
        print(f"   Content: '{content[:50]}...'")
        print(f"   Matched: {terms}")
    
    # Test compound splitting
    print("\n" + "=" * 60)
    print("\nCompound Splitting Tests:")
    for word in ["ReadMessageItem", "context-memory", "snake_case", "XMLParser", "getHTTPResponse"]:
        parts = split_compound(word)
        print(f"  {word} → {parts}")
    
    # Test concept expansion
    print("\n" + "=" * 60)
    print("\nConcept Expansion Tests:")
    for term in ["glicko", "wlxc", "oauth"]:
        related = get_related_concepts(term)
        print(f"  {term} → {related}")
