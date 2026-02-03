#!/usr/bin/env python3
"""
Generate test cases for context-memory validation.

Usage:
    python generate-1000-tests.py              # Generate 2000 tests
    python generate-1000-tests.py --count 1000 # Generate specific count

Sources:
1. Existing test cases (from test-cases-1000.json if exists)
2. Auto-generated from actual transcript content
3. Adversarial cases (things never discussed)
4. Query variations (phrasing, partial, vague)
"""

import json
import re
import random
from pathlib import Path
from collections import defaultdict

TESTS_DIR = Path(__file__).parent
SESSIONS_DIR = Path.home() / ".clawdbot/agents/main/sessions"

# Categories and their target counts (4000 total)
TARGET_COUNTS = {
    "decision": 320,
    "technical": 600,
    "project": 400,
    "identity": 200,
    "adversarial": 1200,  # Important for false positive testing
    "temporal": 120,
    "vague": 320,
    "variation": 400,
    "partial": 240,
    "metadata": 200,
}

# Adversarial topics (things we likely never discussed)
ADVERSARIAL_TOPICS = [
    # Databases
    "Kubernetes", "Redis", "MongoDB", "PostgreSQL", "MySQL", "CockroachDB", "Cassandra", "DynamoDB", "Firestore", "Supabase",
    # Messaging
    "GraphQL", "gRPC", "Kafka", "RabbitMQ", "Elasticsearch", "Pulsar", "NATS", "ZeroMQ", "ActiveMQ",
    # DevOps
    "Terraform", "Ansible", "Puppet", "Chef", "Vagrant", "Packer", "Nomad", "Crossplane",
    # CI/CD
    "Jenkins", "CircleCI", "TravisCI", "GitLab CI", "Bamboo", "TeamCity", "Drone", "Buildkite", "Argo CD",
    # Cloud
    "AWS Lambda", "Azure Functions", "Google Cloud Run", "Heroku", "Vercel", "Netlify", "Cloudflare Workers", "Deno Deploy",
    # Mobile
    "React Native", "Flutter", "Xamarin", "Ionic", "Cordova", "SwiftUI", "Jetpack Compose", "KMM",
    # Frontend
    "Vue.js", "Angular", "Svelte", "Ember", "Backbone", "Solid.js", "Qwik", "Astro", "Next.js", "Remix",
    # Backend
    "Django", "Flask", "FastAPI", "Rails", "Laravel", "Phoenix", "Gin", "Fiber", "Echo", "NestJS",
    # Java
    "Spring Boot", "Hibernate", "JPA", "MyBatis", "Quarkus", "Micronaut", "Vert.x",
    # Auth
    "OAuth2", "SAML", "OpenID", "JWT rotation", "RBAC policies", "Keycloak", "Auth0", "Okta", "Cognito",
    # Deployment
    "Blue-green deployment", "Canary release", "Feature flags", "A/B testing", "Rolling update", "GitOps",
    # Infrastructure
    "Load balancer", "CDN", "WAF", "Rate limiting", "Circuit breaker", "API Gateway", "Service mesh",
    # Service mesh
    "Microservices", "Istio", "Linkerd", "Consul", "Envoy", "Traefik",
    # Data
    "Data lake", "Data warehouse", "ETL pipeline", "Spark", "Hadoop", "Airflow", "Dagster", "Prefect", "dbt",
    # ML
    "Machine learning pipeline", "MLOps", "Model versioning", "Feature store", "MLflow", "Kubeflow", "SageMaker",
    # Web3
    "Blockchain", "Smart contracts", "NFT", "DeFi", "Web3", "Solidity", "Hardhat", "Foundry", "IPFS",
    # XR
    "AR/VR", "Unity", "Unreal Engine", "WebXR", "ARKit", "ARCore", "Oculus SDK",
    # IoT
    "IoT", "MQTT", "Zigbee", "LoRaWAN", "edge computing", "ESP32", "Arduino", "Raspberry Pi",
    # Monitoring
    "Prometheus", "Grafana", "Datadog", "New Relic", "Splunk", "ELK Stack", "Jaeger", "Zipkin",
    # Security
    "Vault", "Secrets Manager", "KMS", "SOPS", "Sealed Secrets", "External Secrets",
    # Testing
    "Cypress", "Playwright", "Selenium", "Jest", "Mocha", "PyTest", "JUnit", "TestNG",
]

ADVERSARIAL_TEMPLATES = [
    "What {topic} configuration are we using?",
    "How did we set up {topic}?",
    "What was the {topic} issue we fixed?",
    "Which {topic} provider did we choose?",
    "What's our {topic} strategy?",
    "How does {topic} integrate with our system?",
    "What {topic} version are we on?",
    "Why did we pick {topic} over alternatives?",
    "What's the {topic} architecture?",
    "How do we handle {topic} failures?",
    "What's the {topic} deployment process?",
    "Where is {topic} documented?",
    "Who manages {topic}?",
    "What's our {topic} approach?",
    "How is {topic} configured?",
]

# Query templates for generating variations
DECISION_TEMPLATES = [
    "What did we decide about {topic}?",
    "Why did we choose {topic}?",
    "What was the decision on {topic}?",
    "How did we resolve the {topic} question?",
    "What approach did we take for {topic}?",
]

TECHNICAL_TEMPLATES = [
    "How does {topic} work?",
    "Where is {topic} configured?",
    "What's the {topic} implementation?",
    "How do we handle {topic}?",
    "What's the {topic} architecture?",
]

PROJECT_TEMPLATES = [
    "What's the status of {topic}?",
    "What phases of {topic} are done?",
    "What bugs did we fix in {topic}?",
    "What features does {topic} have?",
    "Where is {topic} deployed?",
]

def load_existing_tests():
    """Load existing test cases if available."""
    # Try different sources
    for filename in ["test-cases-1000.json", "test-cases.json"]:
        path = TESTS_DIR / filename
        if path.exists():
            with open(path) as f:
                return json.load(f)
    
    # Return empty structure if no existing tests
    return {"testCases": []}

def extract_topics_from_transcripts(limit=100):
    """Extract real topics/terms from transcripts."""
    topics = defaultdict(int)
    
    if not SESSIONS_DIR.exists():
        return []
    
    files = sorted(SESSIONS_DIR.glob("*.jsonl"), 
                   key=lambda f: f.stat().st_mtime, reverse=True)[:limit]
    
    for f in files:
        try:
            with open(f) as fp:
                text = fp.read()
                
                # Extract potential topics (capitalized words, technical terms)
                # Project names
                for match in re.findall(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b', text):
                    topics[match] += 1
                
                # Technical terms
                for match in re.findall(r'\b(wlxc|clawdbot|himalaya|mcporter|ChessRT|context-memory|RLM|JSONL|WSL)\b', text, re.I):
                    topics[match.lower()] += 1
                
                # Paths
                for match in re.findall(r'~/[a-zA-Z0-9_\-/]+', text):
                    if len(match) < 50:
                        topics[match] += 1
                
                # Commands/tools
                for match in re.findall(r'\b(git|npm|python|pip|conda|docker|nerdctl|containerd)\b', text):
                    topics[match] += 1
                    
        except Exception as e:
            pass
    
    # Return sorted by frequency
    return sorted(topics.items(), key=lambda x: x[1], reverse=True)[:200]

def generate_adversarial_cases(count):
    """Generate adversarial test cases (things never discussed)."""
    cases = []
    
    for i in range(count):
        topic = random.choice(ADVERSARIAL_TOPICS)
        template = random.choice(ADVERSARIAL_TEMPLATES)
        query = template.format(topic=topic)
        
        cases.append({
            "id": f"adv{i+1:03d}",
            "category": "adversarial",
            "query": query,
            "expectedKeywords": [],
            "expectedAnswer": f"NOT_FOUND - We never discussed {topic}",
            "sourceDate": None,
            "shouldShowIndicator": False,
            "notes": "Auto-generated adversarial"
        })
    
    return cases

def generate_variation_cases(existing_cases, count):
    """Generate query variations from existing cases."""
    cases = []
    
    # Variations: remove spaces, add underscores, lowercase, typos
    variation_funcs = [
        lambda q: q.lower(),
        lambda q: re.sub(r'[-\s]+', '', q),
        lambda q: re.sub(r'[-\s]+', '_', q),
        lambda q: q.replace("what's", "whats"),
        lambda q: q.replace("?", ""),
        lambda q: re.sub(r'\b(the|a|an)\b', '', q).strip(),
    ]
    
    source_cases = [c for c in existing_cases if c.get("shouldShowIndicator", True)]
    
    for i in range(count):
        source = random.choice(source_cases)
        var_func = random.choice(variation_funcs)
        
        new_query = var_func(source["query"])
        if new_query == source["query"]:
            new_query = source["query"].lower().replace(" ", "-")
        
        cases.append({
            "id": f"var{i+1:03d}",
            "category": "variation",
            "query": new_query,
            "expectedKeywords": source.get("expectedKeywords", [])[:3],
            "expectedAnswer": source.get("expectedAnswer", ""),
            "sourceDate": source.get("sourceDate"),
            "shouldShowIndicator": True,
            "notes": f"Variation of {source['id']}"
        })
    
    return cases

def generate_partial_cases(topics, count):
    """Generate partial/single-word queries."""
    cases = []
    
    # First pass: one per topic
    for i, (topic, freq) in enumerate(topics[:min(count, len(topics))]):
        cases.append({
            "id": f"part{i+1:03d}",
            "category": "partial",
            "query": topic,
            "expectedKeywords": [topic],
            "expectedAnswer": f"Context about {topic}",
            "sourceDate": "YYYY-MM-DD",
            "shouldShowIndicator": True,
            "notes": f"Single keyword query (freq: {freq})"
        })
    
    # Second pass: variations (uppercase, lowercase, partial)
    variations = []
    for topic, freq in topics[:50]:
        if len(topic) > 4:
            variations.append((topic.upper(), topic))
            variations.append((topic[:len(topic)//2+2], topic))  # First half
    
    for i, (query, original) in enumerate(variations[:count - len(cases)]):
        cases.append({
            "id": f"part{len(cases)+1:03d}",
            "category": "partial",
            "query": query,
            "expectedKeywords": [original],
            "expectedAnswer": f"Context about {original}",
            "sourceDate": "YYYY-MM-DD",
            "shouldShowIndicator": True,
            "notes": f"Variation of '{original}'"
        })
    
    return cases[:count]

def generate_vague_cases(count):
    """Generate vague/ambiguous queries."""
    vague_templates = [
        "How do we handle that?",
        "What about the config?",
        "The path thing?",
        "What was that error?",
        "How did we fix it?",
        "What's the setup?",
        "The auth issue?",
        "Container stuff?",
        "The deployment?",
        "Service thing?",
        "That bug?",
        "The workaround?",
        "Integration?",
        "The script?",
        "Config file?",
        "Environment vars?",
        "The timeout issue?",
        "Permissions?",
        "The cache thing?",
        "Startup problem?",
    ]
    
    cases = []
    for i in range(count):
        query = random.choice(vague_templates)
        cases.append({
            "id": f"vague{i+1:03d}",
            "category": "vague",
            "query": query,
            "expectedKeywords": [],
            "expectedAnswer": "Context-dependent",
            "sourceDate": "YYYY-MM-DD",
            "shouldShowIndicator": True,
            "notes": "Vague query requiring semantic matching"
        })
    
    return cases

def generate_temporal_cases(count):
    """Generate time-based queries."""
    templates = [
        "What did we work on yesterday?",
        "What happened last week?",
        "Recent changes?",
        "What did we do today?",
        "This week's progress?",
        "Last session?",
        "Earlier today?",
        "Past few days?",
        "What changed recently?",
        "Latest updates?",
    ]
    
    cases = []
    for i in range(count):
        query = templates[i % len(templates)]
        cases.append({
            "id": f"temp{i+1:03d}",
            "category": "temporal",
            "query": query,
            "expectedKeywords": [],
            "expectedAnswer": "Time-relative context",
            "sourceDate": "YYYY-MM-DD",
            "shouldShowIndicator": True,
            "notes": "Temporal/relative time query"
        })
    
    return cases

def generate_technical_cases(topics, count):
    """Generate technical queries from real topics."""
    cases = []
    
    for i in range(count):
        topic, _ = topics[i % len(topics)]
        template = random.choice(TECHNICAL_TEMPLATES)
        query = template.format(topic=topic)
        
        cases.append({
            "id": f"tech{i+1:03d}",
            "category": "technical",
            "query": query,
            "expectedKeywords": [topic],
            "expectedAnswer": f"Technical details about {topic}",
            "sourceDate": "YYYY-MM-DD",
            "shouldShowIndicator": True,
            "notes": "Auto-generated technical query"
        })
    
    return cases

def generate_decision_cases(topics, count):
    """Generate decision queries."""
    cases = []
    
    for i in range(count):
        topic, _ = topics[i % len(topics)]
        template = random.choice(DECISION_TEMPLATES)
        query = template.format(topic=topic)
        
        cases.append({
            "id": f"dec{i+1:03d}",
            "category": "decision",
            "query": query,
            "expectedKeywords": [topic],
            "expectedAnswer": f"Decision about {topic}",
            "sourceDate": "YYYY-MM-DD",
            "shouldShowIndicator": True,
            "notes": "Auto-generated decision query"
        })
    
    return cases

def generate_project_cases(count):
    """Generate project-related queries."""
    projects = ["wlxc", "ChessRT", "context-memory", "clawdbot", "terminal-relay"]
    
    cases = []
    for i in range(count):
        project = projects[i % len(projects)]
        template = random.choice(PROJECT_TEMPLATES)
        query = template.format(topic=project)
        
        cases.append({
            "id": f"proj{i+1:03d}",
            "category": "project",
            "query": query,
            "expectedKeywords": [project],
            "expectedAnswer": f"Project info about {project}",
            "sourceDate": "YYYY-MM-DD",
            "shouldShowIndicator": True,
            "notes": "Auto-generated project query"
        })
    
    return cases

def generate_identity_cases(count):
    """Generate identity/people queries."""
    people_templates = [
        "Who is {name}?",
        "What does {name} work on?",
        "Who mentioned {name}?",
        "What's {name}'s role?",
        "Who do I know named {name}?",
    ]
    names = [
        "Tucker", "Fei", "Logan", "Austin", "Jon", "Tim", "Mark", "Chris",
        "George", "Angela", "Martin", "Abhilash", "Rohan", "Jordan", "Kent", "Ben",
        "Alex", "Sarah", "Michael", "David", "James", "Robert", "Jennifer", "Lisa",
        "Emily", "Daniel", "Matthew", "Andrew", "Ryan", "Kevin", "Brian", "Jason",
    ]
    
    cases = []
    for i in range(count):
        name = names[i % len(names)]
        template = random.choice(people_templates)
        query = template.format(name=name)
        
        cases.append({
            "id": f"ident{i+1:03d}",
            "category": "identity",
            "query": query,
            "expectedKeywords": [name.lower()],
            "expectedAnswer": f"Info about {name}",
            "sourceDate": "YYYY-MM-DD",
            "shouldShowIndicator": True,
            "notes": "Auto-generated identity query"
        })
    
    return cases

def generate_metadata_cases(count):
    """Generate metadata/system queries."""
    metadata_templates = [
        "Tell me about {skill} skill",
        "What does {skill} do?",
        "How does {skill} work?",
        "What's in {skill}?",
        "Describe the {skill} system",
    ]
    skills = [
        "context-memory", "terminal-relay", "meeting-notes", "qwen-tts", "gsd",
        "weather", "github", "himalaya", "notion", "tmux",
    ]
    
    cases = []
    for i in range(count):
        skill = skills[i % len(skills)]
        template = random.choice(metadata_templates)
        query = template.format(skill=skill)
        
        cases.append({
            "id": f"meta{i+1:03d}",
            "category": "metadata",
            "query": query,
            "expectedKeywords": [skill.replace("-", " ").split()[0]],
            "expectedAnswer": f"Info about {skill}",
            "sourceDate": "YYYY-MM-DD",
            "shouldShowIndicator": True,
            "notes": "Auto-generated metadata query"
        })
    
    return cases

def main():
    total_target = sum(TARGET_COUNTS.values())
    print(f"🧪 Generating {total_target} test cases...")
    
    # Load existing high-quality tests
    existing = load_existing_tests()
    existing_cases = existing["testCases"]
    print(f"  Loaded {len(existing_cases)} existing manual tests")
    
    # Extract topics from transcripts
    topics = extract_topics_from_transcripts(limit=30)
    print(f"  Extracted {len(topics)} topics from transcripts")
    
    all_cases = []
    
    # Keep existing manual tests (renumber)
    for i, case in enumerate(existing_cases):
        case["id"] = f"manual{i+1:03d}"
        case["notes"] = case.get("notes", "") + " [original manual test]"
        all_cases.append(case)
    
    print(f"  Added {len(existing_cases)} manual tests")
    
    # Generate adversarial cases (most important for accuracy)
    adv_cases = generate_adversarial_cases(TARGET_COUNTS["adversarial"])
    all_cases.extend(adv_cases)
    print(f"  Generated {len(adv_cases)} adversarial tests")
    
    # Generate variations (skip if no source cases)
    if existing_cases:
        var_cases = generate_variation_cases(existing_cases, TARGET_COUNTS["variation"])
        all_cases.extend(var_cases)
        print(f"  Generated {len(var_cases)} variation tests")
    else:
        # Generate from topics instead
        var_cases = generate_technical_cases(topics, TARGET_COUNTS["variation"])
        for i, c in enumerate(var_cases):
            c["id"] = f"var{i+1:03d}"
            c["category"] = "variation"
        all_cases.extend(var_cases)
        print(f"  Generated {len(var_cases)} variation tests (from topics, no source cases)")
    
    # Generate technical cases
    tech_cases = generate_technical_cases(topics, TARGET_COUNTS["technical"])
    all_cases.extend(tech_cases)
    print(f"  Generated {len(tech_cases)} technical tests")
    
    # Generate decision cases
    dec_cases = generate_decision_cases(topics, TARGET_COUNTS["decision"])
    all_cases.extend(dec_cases)
    print(f"  Generated {len(dec_cases)} decision tests")
    
    # Generate project cases
    proj_cases = generate_project_cases(TARGET_COUNTS["project"])
    all_cases.extend(proj_cases)
    print(f"  Generated {len(proj_cases)} project tests")
    
    # Generate partial cases
    part_cases = generate_partial_cases(topics, TARGET_COUNTS["partial"])
    all_cases.extend(part_cases)
    print(f"  Generated {len(part_cases)} partial tests")
    
    # Generate vague cases
    vague_cases = generate_vague_cases(TARGET_COUNTS["vague"])
    all_cases.extend(vague_cases)
    print(f"  Generated {len(vague_cases)} vague tests")
    
    # Generate temporal cases
    temp_cases = generate_temporal_cases(TARGET_COUNTS["temporal"])
    all_cases.extend(temp_cases)
    print(f"  Generated {len(temp_cases)} temporal tests")
    
    # Generate identity cases
    ident_cases = generate_identity_cases(TARGET_COUNTS["identity"])
    all_cases.extend(ident_cases)
    print(f"  Generated {len(ident_cases)} identity tests")
    
    # Generate metadata cases
    meta_cases = generate_metadata_cases(TARGET_COUNTS["metadata"])
    all_cases.extend(meta_cases)
    print(f"  Generated {len(meta_cases)} metadata tests")
    
    # Shuffle and trim to target
    total_target = sum(TARGET_COUNTS.values())
    random.shuffle(all_cases)
    all_cases = all_cases[:total_target]
    
    # Renumber all
    for i, case in enumerate(all_cases):
        case["id"] = f"tc{i+1:04d}"
    
    # Create output
    output = {
        "metadata": {
            "created": "2026-01-30",
            "updated": "2026-01-30",
            "description": f"{total_target} test cases for hybrid context retrieval validation",
            "total": len(all_cases),
            "breakdown": {}
        },
        "testCases": all_cases
    }
    
    # Count by category
    for case in all_cases:
        cat = case["category"]
        output["metadata"]["breakdown"][cat] = output["metadata"]["breakdown"].get(cat, 0) + 1
    
    # Save with count in filename
    output_path = TESTS_DIR / f"test-cases-{len(all_cases)}.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✅ Generated {len(all_cases)} test cases")
    print(f"   Saved to: {output_path}")
    print(f"\n📊 Breakdown:")
    for cat, count in sorted(output["metadata"]["breakdown"].items(), key=lambda x: x[1], reverse=True):
        print(f"   {cat}: {count}")

if __name__ == "__main__":
    main()
