#!/usr/bin/env python3
"""
Temporal Query Parser for Context Memory

Parses natural language time references into date ranges.
Cross-platform, no external dependencies.

Usage:
    from temporal_parser import parse_temporal_query
    
    result = parse_temporal_query("what did we discuss yesterday?")
    # Returns: {"type": "relative", "start": "2026-01-29", "end": "2026-01-29", "match": "yesterday"}
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple, List

# Word-form numbers to integers
WORD_NUMBERS = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
    'eleven': 11, 'twelve': 12, 'a': 1, 'an': 1, 'couple': 2,
}

def _word_to_num(word: str) -> int:
    """Convert word-form number to integer."""
    return WORD_NUMBERS.get(word.lower(), 1)

def parse_temporal_query(query: str, reference_date: Optional[datetime] = None) -> Optional[dict]:
    """
    Parse temporal references from a query string.
    
    Args:
        query: Natural language query
        reference_date: Reference date (defaults to now)
    
    Returns:
        dict with {type, start, end, match} or None if no temporal reference found
    """
    if reference_date is None:
        reference_date = datetime.now()
    
    query_lower = query.lower()
    
    # Relative time patterns
    patterns = [
        # Yesterday/today/etc
        (r'\byesterday\b', lambda m, ref: (ref - timedelta(days=1), ref - timedelta(days=1))),
        (r'\btoday\b', lambda m, ref: (ref, ref)),
        (r'\bthis morning\b', lambda m, ref: (ref, ref)),
        (r'\bthis afternoon\b', lambda m, ref: (ref, ref)),
        (r'\bthis evening\b', lambda m, ref: (ref, ref)),
        (r'\btonight\b', lambda m, ref: (ref, ref)),
        
        # Days ago (numeric)
        (r'\b(\d+)\s*days?\s*ago\b', lambda m, ref: (
            ref - timedelta(days=int(m.group(1))),
            ref - timedelta(days=int(m.group(1)))
        )),
        # Days ago (word-form: two days ago, three days ago, etc.)
        (r'\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|a|an|couple)\s*days?\s*ago\b', 
         lambda m, ref: (
            ref - timedelta(days=_word_to_num(m.group(1))),
            ref - timedelta(days=_word_to_num(m.group(1)))
        )),
        (r'\ba\s*few\s*days?\s*ago\b', lambda m, ref: (ref - timedelta(days=3), ref - timedelta(days=2))),
        (r'\bthe\s*other\s*day\b', lambda m, ref: (ref - timedelta(days=3), ref - timedelta(days=1))),
        
        # Week references
        (r'\blast\s*week\b', lambda m, ref: (ref - timedelta(days=ref.weekday() + 7), ref - timedelta(days=ref.weekday() + 1))),
        (r'\bthis\s*week\b', lambda m, ref: (ref - timedelta(days=ref.weekday()), ref)),
        # Weeks ago (numeric)
        (r'\b(\d+)\s*weeks?\s*ago\b', lambda m, ref: (
            ref - timedelta(weeks=int(m.group(1)) + 1),
            ref - timedelta(weeks=int(m.group(1)) - 1)
        )),
        # Weeks ago (word-form: two weeks ago, three weeks ago, etc.)
        (r'\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|a|an|couple)\s*weeks?\s*ago\b',
         lambda m, ref: (
            ref - timedelta(weeks=_word_to_num(m.group(1)) + 1),
            ref - timedelta(weeks=_word_to_num(m.group(1)) - 1)
        )),
        (r'\ba\s*week\s*ago\b', lambda m, ref: (ref - timedelta(days=7), ref - timedelta(days=7))),
        
        # Month references
        (r'\blast\s*month\b', lambda m, ref: _last_month(ref)),
        (r'\bthis\s*month\b', lambda m, ref: _this_month(ref)),
        # Months ago (numeric)
        (r'\b(\d+)\s*months?\s*ago\b', lambda m, ref: _months_ago(ref, int(m.group(1)))),
        # Months ago (word-form: two months ago, three months ago, etc.)
        (r'\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|a|an|couple)\s*months?\s*ago\b',
         lambda m, ref: _months_ago(ref, _word_to_num(m.group(1)))),
        
        # Weekday references
        (r'\bon\s*monday\b', lambda m, ref: _last_weekday(ref, 0)),
        (r'\bon\s*tuesday\b', lambda m, ref: _last_weekday(ref, 1)),
        (r'\bon\s*wednesday\b', lambda m, ref: _last_weekday(ref, 2)),
        (r'\bon\s*thursday\b', lambda m, ref: _last_weekday(ref, 3)),
        (r'\bon\s*friday\b', lambda m, ref: _last_weekday(ref, 4)),
        (r'\bon\s*saturday\b', lambda m, ref: _last_weekday(ref, 5)),
        (r'\bon\s*sunday\b', lambda m, ref: _last_weekday(ref, 6)),
        (r'\blast\s*monday\b', lambda m, ref: _last_weekday(ref, 0)),
        (r'\blast\s*tuesday\b', lambda m, ref: _last_weekday(ref, 1)),
        (r'\blast\s*wednesday\b', lambda m, ref: _last_weekday(ref, 2)),
        (r'\blast\s*thursday\b', lambda m, ref: _last_weekday(ref, 3)),
        (r'\blast\s*friday\b', lambda m, ref: _last_weekday(ref, 4)),
        (r'\blast\s*saturday\b', lambda m, ref: _last_weekday(ref, 5)),
        (r'\blast\s*sunday\b', lambda m, ref: _last_weekday(ref, 6)),
        
        # Last N days (numeric and word-form)
        (r'\blast\s*(\d+)\s*days?\b', lambda m, ref: (
            ref - timedelta(days=int(m.group(1))),
            ref
        )),
        (r'\blast\s*(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|couple|few)\s*days?\b',
         lambda m, ref: (
            ref - timedelta(days=_word_to_num(m.group(1)) if m.group(1) != 'few' else 3),
            ref
        )),
        (r'\bpast\s*(\d+)\s*days?\b', lambda m, ref: (
            ref - timedelta(days=int(m.group(1))),
            ref
        )),
        (r'\bpast\s*(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|couple|few)\s*days?\b',
         lambda m, ref: (
            ref - timedelta(days=_word_to_num(m.group(1)) if m.group(1) != 'few' else 3),
            ref
        )),
        
        # Recent/earlier
        (r'\brecently\b', lambda m, ref: (ref - timedelta(days=7), ref)),
        (r'\bearlier\b', lambda m, ref: (ref - timedelta(days=3), ref)),
        (r'\bpreviously\b', lambda m, ref: (ref - timedelta(days=14), ref - timedelta(days=1))),
        (r'\bbefore\b', lambda m, ref: (ref - timedelta(days=30), ref - timedelta(days=1))),
        
        # Beginning/start of
        (r'\b(beginning|start)\s*of\s*(the\s*)?week\b', lambda m, ref: (ref - timedelta(days=ref.weekday()), ref - timedelta(days=ref.weekday()))),
        (r'\b(beginning|start)\s*of\s*(the\s*)?month\b', lambda m, ref: (ref.replace(day=1), ref.replace(day=1))),
        
        # Specific date patterns (YYYY-MM-DD, MM/DD, etc)
        (r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b', lambda m, ref: _parse_date(m.group(0))),
        (r'\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b', lambda m, ref: _parse_date_mdy(m.group(1), m.group(2), m.group(3), ref)),
        (r'\b(\d{1,2})/(\d{1,2})\b', lambda m, ref: _parse_date_md(m.group(1), m.group(2), ref)),
        
        # Month names (with or without "in" prefix)
        (r'\b(in\s*)?january\b', lambda m, ref: _month_range(ref, 1)),
        (r'\b(in\s*)?february\b', lambda m, ref: _month_range(ref, 2)),
        (r'\b(in\s*)?march\b', lambda m, ref: _month_range(ref, 3)),
        (r'\b(in\s*)?april\b', lambda m, ref: _month_range(ref, 4)),
        (r'\b(in\s*)?may\b', lambda m, ref: _month_range(ref, 5)),
        (r'\b(in\s*)?june\b', lambda m, ref: _month_range(ref, 6)),
        (r'\b(in\s*)?july\b', lambda m, ref: _month_range(ref, 7)),
        (r'\b(in\s*)?august\b', lambda m, ref: _month_range(ref, 8)),
        (r'\b(in\s*)?september\b', lambda m, ref: _month_range(ref, 9)),
        (r'\b(in\s*)?october\b', lambda m, ref: _month_range(ref, 10)),
        (r'\b(in\s*)?november\b', lambda m, ref: _month_range(ref, 11)),
        (r'\b(in\s*)?december\b', lambda m, ref: _month_range(ref, 12)),
        
        # Month abbreviations
        (r'\b(in\s*)?jan\b', lambda m, ref: _month_range(ref, 1)),
        (r'\b(in\s*)?feb\b', lambda m, ref: _month_range(ref, 2)),
        (r'\b(in\s*)?mar\b', lambda m, ref: _month_range(ref, 3)),
        (r'\b(in\s*)?apr\b', lambda m, ref: _month_range(ref, 4)),
        (r'\b(in\s*)?jun\b', lambda m, ref: _month_range(ref, 6)),
        (r'\b(in\s*)?jul\b', lambda m, ref: _month_range(ref, 7)),
        (r'\b(in\s*)?aug\b', lambda m, ref: _month_range(ref, 8)),
        (r'\b(in\s*)?sep\b', lambda m, ref: _month_range(ref, 9)),
        (r'\b(in\s*)?sept\b', lambda m, ref: _month_range(ref, 9)),
        (r'\b(in\s*)?oct\b', lambda m, ref: _month_range(ref, 10)),
        (r'\b(in\s*)?nov\b', lambda m, ref: _month_range(ref, 11)),
        (r'\b(in\s*)?dec\b', lambda m, ref: _month_range(ref, 12)),
    ]
    
    for pattern, handler in patterns:
        match = re.search(pattern, query_lower)
        if match:
            try:
                start, end = handler(match, reference_date)
                return {
                    "type": "relative" if "ago" in pattern or pattern.startswith(r'\b(yesterday|today|last|this|recently)') else "absolute",
                    "start": start.strftime("%Y-%m-%d"),
                    "end": end.strftime("%Y-%m-%d"),
                    "match": match.group(0)
                }
            except (ValueError, AttributeError):
                continue
    
    return None

def _last_weekday(ref: datetime, weekday: int) -> Tuple[datetime, datetime]:
    """Get the most recent occurrence of a weekday."""
    days_ago = (ref.weekday() - weekday) % 7
    if days_ago == 0:
        days_ago = 7  # If today is that day, go back a week
    target = ref - timedelta(days=days_ago)
    return (target, target)

def _last_month(ref: datetime) -> Tuple[datetime, datetime]:
    """Get last month's date range."""
    first_of_this_month = ref.replace(day=1)
    last_of_prev_month = first_of_this_month - timedelta(days=1)
    first_of_prev_month = last_of_prev_month.replace(day=1)
    return (first_of_prev_month, last_of_prev_month)

def _this_month(ref: datetime) -> Tuple[datetime, datetime]:
    """Get this month's date range."""
    first = ref.replace(day=1)
    return (first, ref)

def _months_ago(ref: datetime, months: int) -> Tuple[datetime, datetime]:
    """Get date range for N months ago."""
    year = ref.year
    month = ref.month - months
    while month <= 0:
        month += 12
        year -= 1
    start = ref.replace(year=year, month=month, day=1)
    if month == 12:
        end = ref.replace(year=year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end = ref.replace(year=year, month=month + 1, day=1) - timedelta(days=1)
    return (start, end)

def _month_range(ref: datetime, month: int) -> Tuple[datetime, datetime]:
    """Get date range for a specific month."""
    year = ref.year if month <= ref.month else ref.year - 1
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = datetime(year, month + 1, 1) - timedelta(days=1)
    return (start, end)

def _parse_date(date_str: str) -> Tuple[datetime, datetime]:
    """Parse YYYY-MM-DD format."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return (dt, dt)

def _parse_date_mdy(month: str, day: str, year: str, ref: datetime) -> Tuple[datetime, datetime]:
    """Parse MM/DD/YY or MM/DD/YYYY format."""
    y = int(year)
    if y < 100:
        y += 2000 if y < 50 else 1900
    dt = datetime(y, int(month), int(day))
    return (dt, dt)

def _parse_date_md(month: str, day: str, ref: datetime) -> Tuple[datetime, datetime]:
    """Parse MM/DD format (assumes current or previous year)."""
    dt = datetime(ref.year, int(month), int(day))
    if dt > ref:
        dt = datetime(ref.year - 1, int(month), int(day))
    return (dt, dt)

def filter_sessions_by_date(sessions: dict, start_date: str, end_date: str) -> List[str]:
    """
    Filter session IDs by date range.
    
    Args:
        sessions: Dict of session_id -> session_info (with 'date' field)
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
    
    Returns:
        List of matching session IDs
    """
    matching = []
    for session_id, info in sessions.items():
        session_date = info.get("date", "")
        if start_date <= session_date <= end_date:
            matching.append(session_id)
    return matching

# CLI for testing
if __name__ == "__main__":
    import sys
    
    test_queries = [
        "what did we work on yesterday?",
        "what did we discuss last week?",
        "when did we talk about auth?",
        "show me the conversation from 3 days ago",
        "what happened on Monday?",
        "find discussions from January",
        "what were we doing this morning?",
        "conversations from 2026-01-15",
        "what did we decide recently?",
    ]
    
    if len(sys.argv) > 1:
        test_queries = [" ".join(sys.argv[1:])]
    
    print("Temporal Query Parser Test\n")
    ref = datetime.now()
    print(f"Reference date: {ref.strftime('%Y-%m-%d %H:%M')}\n")
    
    for query in test_queries:
        result = parse_temporal_query(query, ref)
        if result:
            print(f"✓ \"{query}\"")
            print(f"  → {result['start']} to {result['end']} (matched: '{result['match']}')")
        else:
            print(f"✗ \"{query}\"")
            print(f"  → No temporal reference found")
        print()
