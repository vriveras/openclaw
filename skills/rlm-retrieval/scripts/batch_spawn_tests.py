#!/usr/bin/env python3
"""
Batch spawn sub-agents for in-session skill validation.
Run from OpenClaw session, collect results.
"""

import json
import time
from pathlib import Path

# Test queries - diverse set for validation
QUERIES = [
    # Projects (20)
    "What is WLXC?", "Tell me about ChessRT", "context-memory skill details",
    "WorkIQ integration", "Cat-Tic-Toe game", "IDC proposal", "Alt-Text feature",
    "OpenClaw configuration", "blog post we wrote", "personal blog site",
    "native gateway project", "skill automation work", "meeting transcription setup",
    "Himalaya email", "qwen-tts voice", "gsd workflow", "spec-planner skill",
    "terminal relay usage", "BlueBubbles plugin", "mcporter MCP",
    
    # Temporal (15)
    "What did we work on yesterday?", "projects this week", "last week summary",
    "January 30 work", "today's progress", "recent conversations",
    "what happened Monday", "Tuesday discussions", "this morning's tasks",
    "overnight changes", "weekend work", "last 3 days", "recent commits",
    "yesterday's meetings", "earlier today",
    
    # People (15)
    "Tucker conversations", "Logan discussions", "Fei Su 1:1",
    "Cary messages", "Gabriel chat", "team discussions",
    "direct report updates", "manager feedback", "who mentioned ratings",
    "who worked on containers", "conversations with family",
    "Angela updates", "Chris discussions", "Austin work", "Mark feedback",
    
    # Technical (25)
    "Glicko-2 rating", "containerd setup", "MongoDB config", "WebSocket code",
    "binfmt fix", "WSL configuration", "Windows interop", "tmux sessions",
    "Python dependencies", "Node.js setup", "TypeScript errors", "React components",
    "API endpoints", "REST vs gRPC", "Docker containers", "Redis cache",
    "PostgreSQL queries", "JSON parsing", "YAML config", "Markdown formatting",
    "git commits", "GitHub PRs", "CI/CD pipeline", "test coverage", "deployment",
    
    # Topics (20)
    "inbox triage", "Teams notifications", "calendar conflicts", "email setup",
    "heartbeat checks", "cron jobs", "session indexing", "memory search",
    "skill validation", "accuracy metrics", "test results", "blog writing",
    "documentation updates", "code review", "bug fixes", "feature requests",
    "performance optimization", "error handling", "logging setup", "monitoring",
    
    # Fuzzy/partial (15)
    "the container thing", "rating system", "memory accuracy",
    "that blog post", "the chess app", "voice synthesis",
    "email client", "calendar thing", "teams stuff",
    "the skill we built", "testing approach", "validation numbers",
    "search functionality", "matching algorithm", "indexing process",
]

def generate_spawn_commands():
    """Generate sessions_spawn commands for each query."""
    commands = []
    for i, query in enumerate(QUERIES):
        label = f"skill-test-{i+1:03d}"
        task = f'Use the context-memory skill to answer: "{query}". Search memory and report what you found. Note if the skill triggered successfully.'
        commands.append({
            "query": query,
            "label": label,
            "task": task
        })
    return commands

if __name__ == "__main__":
    commands = generate_spawn_commands()
    print(f"Generated {len(commands)} test commands")
    
    # Save for reference
    output = Path(__file__).parent.parent / "tests" / "spawn_commands.json"
    output.parent.mkdir(exist_ok=True)
    with open(output, 'w') as f:
        json.dump(commands, f, indent=2)
    print(f"Saved to {output}")
    
    # Print sample
    print("\nSample commands:")
    for cmd in commands[:3]:
        print(f"  {cmd['label']}: {cmd['query'][:40]}...")
