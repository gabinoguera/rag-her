from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.utils.text_processing import clean_whitespace, normalize_unicode

ABBREVIATION_EXPANSIONS: dict[str, str] = {
    "JWT": "JWT (JSON Web Token)",
    "API": "API (Application Programming Interface)",
    "REST": "REST (Representational State Transfer)",
    "CRUD": "CRUD (Create, Read, Update, Delete)",
    "CI/CD": "CI/CD (Continuous Integration/Continuous Deployment)",
    "OAuth": "OAuth (Open Authorization)",
    "SSO": "SSO (Single Sign-On)",
    "PWA": "PWA (Progressive Web App)",
    "SPA": "SPA (Single Page Application)",
    "ORM": "ORM (Object-Relational Mapping)",
    "CDN": "CDN (Content Delivery Network)",
    "E2E": "E2E (End to End)",
    "QA": "QA (Quality Assurance)",
    "UX": "UX (User Experience)",
    "UI": "UI (User Interface)",
    "MVP": "MVP (Minimum Viable Product)",
    "OCR": "OCR (Optical Character Recognition)",
    "NLP": "NLP (Natural Language Processing)",
}

TECHNOLOGY_ALIASES: dict[str, str] = {
    # JavaScript ecosystem
    "react": "React",
    "reactjs": "React",
    "react.js": "React",
    "vue": "Vue.js",
    "vuejs": "Vue.js",
    "vue.js": "Vue.js",
    "angular": "Angular",
    "angularjs": "Angular",
    "next": "Next.js",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "express": "Express",
    "expressjs": "Express",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    # Python ecosystem
    "python": "Python",
    "django": "Django",
    "fastapi": "FastAPI",
    "flask": "Flask",
    # Ruby
    "rails": "Ruby on Rails",
    "ruby on rails": "Ruby on Rails",
    "ror": "Ruby on Rails",
    # Databases
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "elasticsearch": "Elasticsearch",
    # Cloud & DevOps
    "aws": "AWS",
    "gcp": "GCP",
    "azure": "Azure",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    # Mobile
    "react native": "React Native",
    "flutter": "Flutter",
    "swift": "Swift",
    "kotlin": "Kotlin",
    # AI/ML
    "openai": "OpenAI API",
    "langchain": "LangChain",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    # Payments & Services
    "stripe": "Stripe",
    "firebase": "Firebase",
    # CSS
    "tailwind": "Tailwind CSS",
    "tailwindcss": "Tailwind CSS",
    # Others
    "graphql": "GraphQL",
    "pgvector": "pgvector",
    "sidekiq": "Sidekiq",
    "chart.js": "Chart.js",
}

CHUNK_TYPE_KEYWORDS: dict[str, list[str]] = {
    "scope_block": ["coste", "costo", "presupuesto", "precio", "bloque", "modulo", "funcionalidad"],
    "line_item": ["coste", "costo", "presupuesto", "precio", "tarea", "item", "partida"],
    "team_conditions": ["equipo", "team", "condiciones", "pago", "dedicacion"],
    "phase": ["fase", "phase", "etapa", "roadmap", "hito", "milestone"],
    "project_overview": ["proyecto", "resumen", "overview", "general", "tecnologias"],
}


def _expand_abbreviations(text: str) -> str:
    """Expand abbreviations, replacing first occurrence only if not already expanded."""
    for abbr, expansion in ABBREVIATION_EXPANSIONS.items():
        # Skip if already expanded (expansion text present)
        if expansion in text:
            continue
        # Replace first occurrence using word boundary
        pattern = re.compile(r"\b" + re.escape(abbr) + r"\b")
        text = pattern.sub(expansion, text, count=1)
    return text


def _detect_technologies(text: str) -> list[str]:
    """Detect technologies in text using aliases. Case-insensitive with word boundary."""
    detected: list[str] = []
    seen: set[str] = set()
    text_lower = text.lower()

    for alias, canonical in TECHNOLOGY_ALIASES.items():
        if canonical in seen:
            continue
        # Word boundary match (case insensitive)
        pattern = re.compile(r"\b" + re.escape(alias) + r"\b", re.IGNORECASE)
        if pattern.search(text_lower):
            seen.add(canonical)
            detected.append(canonical)

    return detected


def _suggest_chunk_types(text: str) -> list[str]:
    """Suggest chunk types based on keyword matching in query text."""
    text_lower = text.lower()
    matched_types: set[str] = set()

    for chunk_type, keywords in CHUNK_TYPE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                matched_types.add(chunk_type)
                break

    if not matched_types:
        return list(CHUNK_TYPE_KEYWORDS.keys())

    return sorted(matched_types)


@dataclass
class PreprocessedQuery:
    original_text: str
    processed_text: str
    detected_technologies: list[str] = field(default_factory=list)
    suggested_chunk_types: list[str] = field(default_factory=list)


def preprocess_query(query: str) -> PreprocessedQuery:
    """Full preprocessing pipeline for search queries."""
    original = query
    text = normalize_unicode(query)
    text = clean_whitespace(text)
    text = _expand_abbreviations(text)

    detected_techs = _detect_technologies(text)
    suggested_types = _suggest_chunk_types(text)

    return PreprocessedQuery(
        original_text=original,
        processed_text=text,
        detected_technologies=detected_techs,
        suggested_chunk_types=suggested_types,
    )
