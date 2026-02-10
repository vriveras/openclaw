#!/usr/bin/env python3
"""
Generate synthetic test chunks and queries for Claude Code context-memory validation.

Creates:
1. .claude-memory/conv-*.md chunks with realistic content
2. test-cases.json with queries that should/shouldn't match

Usage:
    python generate-test-chunks.py --output /tmp/test-claude-memory --count 50
"""

import argparse
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

# Realistic topics and content patterns
TOPICS = {
    "auth": {
        "keywords": ["oauth", "authentication", "login", "jwt", "token", "session", "credentials"],
        "content": [
            "Discussed OAuth2 PKCE flow for the mobile app authentication.",
            "Decided to use JWT tokens with 15-minute expiry for security.",
            "The login flow needs to handle MFA through authenticator apps.",
            "Session management will use httpOnly cookies to prevent XSS.",
        ]
    },
    "database": {
        "keywords": ["postgres", "postgresql", "sql", "migration", "schema", "index"],
        "content": [
            "PostgreSQL is our primary database, running version 15.",
            "Added index on users.email for faster lookups.",
            "Migration strategy: use flyway for version control.",
            "Schema design follows normalized form up to 3NF.",
        ]
    },
    "api": {
        "keywords": ["rest", "endpoint", "graphql", "request", "response", "rate-limit"],
        "content": [
            "REST API follows OpenAPI 3.0 spec.",
            "Rate limiting set to 100 requests per minute per user.",
            "GraphQL available for complex nested queries.",
            "All endpoints require Bearer token authentication.",
        ]
    },
    "deployment": {
        "keywords": ["docker", "kubernetes", "k8s", "container", "deploy", "ci/cd"],
        "content": [
            "Docker images pushed to private registry.",
            "Kubernetes deployment uses rolling updates.",
            "CI/CD pipeline runs tests before any deploy.",
            "Container health checks on /health endpoint.",
        ]
    },
    "testing": {
        "keywords": ["unit", "integration", "e2e", "coverage", "jest", "pytest"],
        "content": [
            "Unit tests required for all new functions.",
            "Integration tests run against test database.",
            "E2E tests use Playwright for browser automation.",
            "Coverage threshold set at 80% minimum.",
        ]
    },
    "frontend": {
        "keywords": ["react", "component", "state", "redux", "css", "typescript"],
        "content": [
            "React 18 with TypeScript for type safety.",
            "State management using Redux Toolkit.",
            "CSS modules for component-scoped styles.",
            "Component library based on Radix primitives.",
        ]
    },
    "performance": {
        "keywords": ["cache", "redis", "latency", "optimization", "memory", "cpu"],
        "content": [
            "Redis cache for session data and hot queries.",
            "P99 latency target is under 200ms.",
            "Memory optimization reduced heap by 40%.",
            "CPU profiling identified N+1 query issues.",
        ]
    },
    "security": {
        "keywords": ["encryption", "ssl", "tls", "vulnerability", "audit", "pentest"],
        "content": [
            "All data encrypted at rest with AES-256.",
            "TLS 1.3 required for all connections.",
            "Security audit scheduled for Q2.",
            "Penetration testing by external firm annually.",
        ]
    },
}

# People/entities for identity queries
PEOPLE = [
    ("Alex", "frontend lead", "React architecture"),
    ("Jordan", "backend engineer", "API development"),
    ("Sam", "DevOps", "Kubernetes and CI/CD"),
    ("Taylor", "security engineer", "authentication system"),
    ("Casey", "DBA", "PostgreSQL optimization"),
    ("Morgan", "QA lead", "testing strategy"),
    ("Riley", "product manager", "feature prioritization"),
    ("Quinn", "tech lead", "architecture decisions"),
]

# Adversarial topics (things we won't generate content about)
ADVERSARIAL = [
    "MongoDB", "MySQL", "Angular", "Vue", "AWS Lambda", "Azure Functions",
    "Terraform", "Ansible", "Jenkins", "CircleCI", "Kafka", "RabbitMQ",
    "Elasticsearch", "Solr", "Cassandra", "DynamoDB", "Firebase",
]

def generate_chunk(date: datetime, topics: list, people: list) -> str:
    """Generate a realistic conversation chunk."""
    lines = [
        f"# Conversation - {date.strftime('%Y-%m-%d')}",
        "",
        f"**Date:** {date.strftime('%B %d, %Y')}",
        f"**Summary:** Discussion about {', '.join(t for t in topics[:2])}",
        "",
    ]
    
    # Add topic sections
    for topic in topics:
        if topic in TOPICS:
            info = TOPICS[topic]
            lines.append(f"## {topic.title()}")
            lines.append("")
            for content in random.sample(info["content"], min(2, len(info["content"]))):
                lines.append(f"- {content}")
            lines.append("")
    
    # Add people mentions
    if people and random.random() > 0.5:
        lines.append("## Team Notes")
        lines.append("")
        for person, role, focus in random.sample(people, min(2, len(people))):
            lines.append(f"- {person} ({role}) working on {focus}")
        lines.append("")
    
    # Add decisions section
    if random.random() > 0.3:
        lines.append("## Decisions")
        lines.append("")
        topic = random.choice(topics)
        if topic in TOPICS:
            lines.append(f"- Decided: {random.choice(TOPICS[topic]['content'])}")
        lines.append("")
    
    return "\n".join(lines)


def generate_test_cases(chunks_info: list, count: int = 500, memory_dir: Path = None) -> list:
    """Generate test queries based on created chunks."""
    test_cases = []
    case_id = 0
    
    # Read actual chunk content to find real keywords
    chunk_keywords = {}
    if memory_dir:
        for chunk in chunks_info:
            chunk_path = memory_dir / chunk["file"]
            if chunk_path.exists():
                content = chunk_path.read_text().lower()
                found = []
                for topic in chunk["topics"]:
                    if topic in TOPICS:
                        for kw in TOPICS[topic]["keywords"]:
                            if kw.lower() in content:
                                found.append(kw)
                chunk_keywords[chunk["file"]] = found
    
    # Positive cases - queries that SHOULD match
    for chunk in chunks_info:
        # Get keywords actually in this chunk
        actual_keywords = chunk_keywords.get(chunk["file"], [])
        
        for topic in chunk["topics"]:
            if topic in TOPICS:
                # Find keywords from this topic that are in the chunk
                topic_keywords = [kw for kw in TOPICS[topic]["keywords"] if kw in actual_keywords]
                if not topic_keywords:
                    topic_keywords = TOPICS[topic]["keywords"][:1]  # Fallback
                
                # Direct keyword query
                keyword = random.choice(topic_keywords)
                case_id += 1
                test_cases.append({
                    "id": f"tc{case_id:04d}",
                    "category": "technical",
                    "query": f"What's our {keyword} setup?",
                    "expectedKeywords": [keyword],
                    "shouldMatch": True,
                    "sourceDate": chunk["date"],
                })
                
                # Variation query - only use keywords we know are in the chunk
                if len(topic_keywords) > 0:
                    keyword2 = random.choice(topic_keywords)
                    case_id += 1
                    test_cases.append({
                        "id": f"tc{case_id:04d}",
                        "category": "variation",
                        "query": f"How did we set up {keyword2}?",
                        "expectedKeywords": [keyword2],
                        "shouldMatch": True,
                        "sourceDate": chunk["date"],
                    })
        
        # People queries
        for person, role, focus in chunk.get("people", []):
            case_id += 1
            test_cases.append({
                "id": f"tc{case_id:04d}",
                "category": "identity",
                "query": f"What does {person} work on?",
                "expectedKeywords": [person.lower()],
                "shouldMatch": True,
                "sourceDate": chunk["date"],
            })
    
    # Temporal queries
    dates = sorted(set(c["date"] for c in chunks_info))
    if dates:
        case_id += 1
        test_cases.append({
            "id": f"tc{case_id:04d}",
            "category": "temporal",
            "query": "What did we discuss yesterday?",
            "expectedKeywords": [],
            "shouldMatch": True,
            "temporalFilter": "yesterday",
        })
        case_id += 1
        test_cases.append({
            "id": f"tc{case_id:04d}",
            "category": "temporal", 
            "query": "What happened last week?",
            "expectedKeywords": [],
            "shouldMatch": True,
            "temporalFilter": "last_week",
        })
    
    # Adversarial cases - queries that should NOT match
    for adv_topic in ADVERSARIAL:
        case_id += 1
        test_cases.append({
            "id": f"tc{case_id:04d}",
            "category": "adversarial",
            "query": f"What's our {adv_topic} configuration?",
            "expectedKeywords": [],
            "shouldMatch": False,
            "note": f"We never discussed {adv_topic}",
        })
    
    # Shuffle and limit
    random.shuffle(test_cases)
    return test_cases[:count]


def main():
    parser = argparse.ArgumentParser(description="Generate test data for Claude Code context-memory")
    parser.add_argument("--output", "-o", default="/tmp/test-claude-memory", help="Output directory")
    parser.add_argument("--chunks", "-c", type=int, default=30, help="Number of chunks to generate")
    parser.add_argument("--tests", "-t", type=int, default=500, help="Number of test cases")
    parser.add_argument("--days", "-d", type=int, default=30, help="Days of history to simulate")
    
    args = parser.parse_args()
    
    output_dir = Path(args.output)
    memory_dir = output_dir / ".claude-memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate chunks
    chunks_info = []
    base_date = datetime.now()
    
    for i in range(args.chunks):
        # Random date within range
        days_ago = random.randint(0, args.days)
        chunk_date = base_date - timedelta(days=days_ago)
        
        # Random topics (2-4 per chunk)
        topics = random.sample(list(TOPICS.keys()), random.randint(2, 4))
        
        # Random people (0-3 per chunk)
        people = random.sample(PEOPLE, random.randint(0, 3))
        
        # Generate content
        content = generate_chunk(chunk_date, topics, people)
        
        # Save chunk
        chunk_num = i + 1
        chunk_name = f"conv-{chunk_date.strftime('%Y-%m-%d')}-{chunk_num:03d}.md"
        chunk_path = memory_dir / chunk_name
        chunk_path.write_text(content)
        
        chunks_info.append({
            "file": chunk_name,
            "date": chunk_date.strftime("%Y-%m-%d"),
            "topics": topics,
            "people": people,
        })
    
    print(f"✅ Generated {len(chunks_info)} chunks in {memory_dir}")
    
    # Generate initial state
    state = {
        "lastUpdated": datetime.now().isoformat(),
        "activeTopics": random.sample(list(TOPICS.keys()), 3),
        "openThreads": [],
        "recentDecisions": [],
        "entities": {},
        "pendingFollowups": [],
    }
    
    state_path = memory_dir / "state.json"
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)
    
    print(f"✅ Generated state.json")
    
    # Generate test cases
    test_cases = generate_test_cases(chunks_info, args.tests, memory_dir)
    
    tests_output = {
        "metadata": {
            "created": datetime.now().isoformat(),
            "generator": "generate-test-chunks.py",
            "chunkCount": len(chunks_info),
            "testCount": len(test_cases),
        },
        "testCases": test_cases,
    }
    
    tests_path = output_dir / "test-cases.json"
    with open(tests_path, "w") as f:
        json.dump(tests_output, f, indent=2)
    
    print(f"✅ Generated {len(test_cases)} test cases in {tests_path}")
    
    # Summary by category
    categories = {}
    for tc in test_cases:
        cat = tc.get("category", "other")
        categories[cat] = categories.get(cat, 0) + 1
    
    print(f"\nTest breakdown:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
