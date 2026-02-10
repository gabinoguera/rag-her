"""Seed data script — loads 3 sample budgets into the database.

Usage:
    python scripts/seed_data.py

Requires a running PostgreSQL + .env with OPENAI_API_KEY.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.schemas.quote_input import IngestRequest  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.core.embeddings import EmbeddingService  # noqa: E402
from app.db import get_session_factory, init_db  # noqa: E402
from app.services.ingest_service import DuplicateError, IngestService  # noqa: E402

QUOTES: list[dict] = [
    {
        "quote": {
            "client": {"company": "TechVision Labs"},
            "project": {
                "title": "Plataforma IA Conversacional",
                "subtitle": "Sistema de IA con chatbot y analisis de documentos",
            },
            "currency": "EUR",
            "objectives": [
                {"title": "Automatizar atencion al cliente con IA"},
                {"title": "Reducir tiempos de respuesta en un 70%"},
            ],
            "scope_blocks": [
                {
                    "title": "Backend API",
                    "short_description": "API REST con Rails y autenticacion JWT",
                    "technologies": ["Ruby on Rails", "PostgreSQL", "Redis"],
                    "features": ["Auth JWT", "Rate limiting", "Webhooks"],
                },
                {
                    "title": "Frontend SPA",
                    "short_description": "Interfaz React con dashboards interactivos",
                    "technologies": ["React", "TypeScript", "TailwindCSS"],
                    "features": ["Dashboard interactivo", "Tema claro/oscuro"],
                },
                {
                    "title": "Modulo IA",
                    "short_description": "Chatbot conversacional y analisis de documentos",
                    "technologies": ["Python", "OpenAI", "LangChain", "pgvector"],
                    "features": ["Chatbot con memoria", "Analisis de PDFs"],
                },
            ],
            "roadmap_phases": [
                {"name": "Diseno", "duration": "2 semanas"},
                {"name": "Backend", "duration": "4 semanas"},
                {"name": "Frontend", "duration": "3 semanas"},
                {"name": "IA", "duration": "2 semanas"},
                {"name": "Testing", "duration": "1 semana"},
            ],
            "items": [
                {"type": "service", "name": "Analisis y diseno", "quantity": 5, "unit": "dia", "unit_price": 500, "phase": "Diseno"},
                {"type": "service", "name": "Desarrollo Backend", "quantity": 15, "unit": "dia", "unit_price": 500, "phase": "Backend"},
                {"type": "service", "name": "Desarrollo Frontend", "quantity": 12, "unit": "dia", "unit_price": 450, "phase": "Frontend"},
                {"type": "service", "name": "Integracion IA", "quantity": 8, "unit": "dia", "unit_price": 550, "phase": "IA"},
                {"type": "service", "name": "QA y Testing", "quantity": 4, "unit": "dia", "unit_price": 400, "phase": "Testing"},
            ],
            "team_members": [
                {"profile_type": "Tech Lead", "quantity": 1, "dedication": "full_time"},
                {"profile_type": "Full Stack Dev", "quantity": 2, "dedication": "full_time"},
            ],
            "conditions": {
                "payment_terms": ["30% inicio", "40% entrega parcial", "30% entrega final"],
            },
        },
        "source": "seed_script",
    },
    {
        "quote": {
            "client": {"company": "MarketFlow Inc"},
            "project": {
                "title": "E-commerce Marketplace",
                "subtitle": "Marketplace multivendor con pagos integrados",
            },
            "currency": "EUR",
            "objectives": [
                {"title": "Lanzar marketplace multivendor en 4 meses"},
                {"title": "Integrar pasarela de pagos Stripe"},
            ],
            "scope_blocks": [
                {
                    "title": "Backend Marketplace",
                    "short_description": "API Node.js con gestion de vendedores y productos",
                    "technologies": ["Node.js", "Express", "PostgreSQL", "Redis"],
                    "features": ["Gestion de vendedores", "Catalogo de productos", "Busqueda avanzada"],
                },
                {
                    "title": "Frontend Marketplace",
                    "short_description": "SPA Vue.js con carrito y checkout",
                    "technologies": ["Vue.js", "TypeScript", "TailwindCSS"],
                    "features": ["Carrito de compras", "Checkout multi-paso", "Panel vendedor"],
                },
                {
                    "title": "Pagos y Logistica",
                    "short_description": "Integracion con Stripe y sistema de envios",
                    "technologies": ["Stripe", "Node.js"],
                    "features": ["Split payments", "Facturacion automatica", "Tracking envios"],
                },
                {
                    "title": "Buscador",
                    "short_description": "Motor de busqueda con Elasticsearch",
                    "technologies": ["Elasticsearch", "Node.js"],
                    "features": ["Busqueda full-text", "Filtros avanzados", "Sugerencias"],
                },
            ],
            "roadmap_phases": [
                {"name": "Arquitectura", "duration": "2 semanas"},
                {"name": "Core Backend", "duration": "6 semanas"},
                {"name": "Frontend", "duration": "4 semanas"},
                {"name": "Pagos", "duration": "3 semanas"},
                {"name": "QA y Launch", "duration": "2 semanas"},
            ],
            "items": [
                {"type": "service", "name": "Arquitectura del sistema", "quantity": 8, "unit": "dia", "unit_price": 550, "phase": "Arquitectura"},
                {"type": "service", "name": "Backend core", "quantity": 25, "unit": "dia", "unit_price": 500, "phase": "Core Backend"},
                {"type": "service", "name": "Frontend Vue.js", "quantity": 18, "unit": "dia", "unit_price": 450, "phase": "Frontend"},
                {"type": "service", "name": "Integracion Stripe", "quantity": 10, "unit": "dia", "unit_price": 550, "phase": "Pagos"},
                {"type": "service", "name": "Testing y despliegue", "quantity": 8, "unit": "dia", "unit_price": 400, "phase": "QA y Launch"},
            ],
            "team_members": [
                {"profile_type": "Tech Lead", "quantity": 1, "dedication": "full_time"},
                {"profile_type": "Backend Dev", "quantity": 2, "dedication": "full_time"},
                {"profile_type": "Frontend Dev", "quantity": 1, "dedication": "full_time"},
                {"profile_type": "QA", "quantity": 1, "dedication": "part_time"},
            ],
            "conditions": {
                "payment_terms": ["25% inicio", "25% mes 1", "25% mes 2", "25% entrega"],
            },
        },
        "source": "seed_script",
    },
    {
        "quote": {
            "client": {"company": "FitLife Digital"},
            "project": {
                "title": "App Fitness y Bienestar",
                "subtitle": "Aplicacion movil de fitness con seguimiento y comunidad",
            },
            "currency": "EUR",
            "objectives": [
                {"title": "App movil multiplataforma con React Native"},
                {"title": "Gamificacion y sistema de logros"},
            ],
            "scope_blocks": [
                {
                    "title": "Backend Firebase",
                    "short_description": "Backend serverless con Firebase y Node.js",
                    "technologies": ["Firebase", "Node.js", "MongoDB"],
                    "features": ["Auth social", "Push notifications", "Cloud Functions"],
                },
                {
                    "title": "App Movil",
                    "short_description": "App React Native con tracking de ejercicios",
                    "technologies": ["React Native", "TypeScript"],
                    "features": ["Tracking ejercicios", "Planes personalizados", "Calendario"],
                },
                {
                    "title": "Comunidad",
                    "short_description": "Red social interna con retos y logros",
                    "technologies": ["React Native", "Firebase"],
                    "features": ["Feed social", "Retos grupales", "Sistema de logros"],
                },
            ],
            "roadmap_phases": [
                {"name": "UX Research", "duration": "2 semanas"},
                {"name": "Core Dev", "duration": "5 semanas"},
                {"name": "Social Features", "duration": "3 semanas"},
                {"name": "Polish & Launch", "duration": "2 semanas"},
            ],
            "items": [
                {"type": "service", "name": "UX Research y prototipos", "quantity": 8, "unit": "dia", "unit_price": 450, "phase": "UX Research"},
                {"type": "service", "name": "Desarrollo core app", "quantity": 20, "unit": "dia", "unit_price": 500, "phase": "Core Dev"},
                {"type": "service", "name": "Features sociales", "quantity": 12, "unit": "dia", "unit_price": 450, "phase": "Social Features"},
                {"type": "service", "name": "QA y publicacion stores", "quantity": 6, "unit": "dia", "unit_price": 400, "phase": "Polish & Launch"},
            ],
            "team_members": [
                {"profile_type": "Mobile Lead", "quantity": 1, "dedication": "full_time"},
                {"profile_type": "Mobile Dev", "quantity": 1, "dedication": "full_time"},
                {"profile_type": "UX Designer", "quantity": 1, "dedication": "part_time"},
            ],
            "conditions": {
                "payment_terms": ["40% inicio", "30% entrega beta", "30% entrega final"],
            },
        },
        "source": "seed_script",
    },
]


async def main() -> None:
    settings = get_settings()
    init_db(settings)

    embedding_service = EmbeddingService(
        api_key=settings.OPENAI_API_KEY,
        model=settings.EMBEDDING_MODEL,
        dimensions=settings.EMBEDDING_DIMENSIONS,
    )

    factory = get_session_factory()

    for i, quote_data in enumerate(QUOTES, 1):
        async with factory() as session:
            service = IngestService(db=session, embedding_service=embedding_service)
            request = IngestRequest(**quote_data)
            try:
                result = service.ingest_quote(request)
                if asyncio.iscoroutine(result):
                    result = await result
                print(
                    f"[{i}/{len(QUOTES)}] Ingested: {quote_data['quote']['project']['title']} "
                    f"-> {result.chunks_count} chunks ({result.processing_time_ms}ms)"
                )
            except DuplicateError:
                print(
                    f"[{i}/{len(QUOTES)}] Skipped (duplicate): "
                    f"{quote_data['quote']['project']['title']}"
                )


if __name__ == "__main__":
    asyncio.run(main())
