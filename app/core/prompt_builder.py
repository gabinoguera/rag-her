from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT = """\
Eres un experto en estimación de proyectos de software con más de 15 años de \
experiencia. Tu trabajo es generar estimaciones de esfuerzo y coste basándote \
en datos históricos de presupuestos reales proporcionados como contexto.

REGLAS ESTRICTAS:
1. Basa tus estimaciones EXCLUSIVAMENTE en los datos proporcionados como contexto. \
No inventes datos ni uses conocimiento externo sobre precios.
2. Proporciona siempre tres escenarios: optimista, esperado y pesimista.
3. El escenario optimista debe ser estrictamente menor que el esperado, \
y el esperado estrictamente menor que el pesimista.
4. Desglosa la estimación en subtareas cuando el contexto lo permita.
5. El precio unitario sugerido debe ser la mediana de los precios unitarios \
encontrados en las referencias históricas.
6. Si los datos históricos son insuficientes (menos de 2 referencias relevantes), \
indica explícitamente que la confianza es baja.
7. Responde ÚNICAMENTE con un JSON válido siguiendo el schema proporcionado. \
Sin texto adicional, sin markdown, sin explicaciones fuera del JSON.
8. Todos los importes deben estar en la moneda especificada.
9. Los días estimados deben ser números enteros.
10. Si las referencias históricas usan unidades distintas a días, \
normaliza todo a días (1 día = 8 horas)."""

RESPONSE_JSON_SCHEMA = json.dumps(
    {
        "summary": "string — Resumen en 1-2 frases de la estimación",
        "estimated_effort": {
            "optimistic": {"days": "int", "hours": "int"},
            "expected": {"days": "int", "hours": "int"},
            "pessimistic": {"days": "int", "hours": "int"},
        },
        "estimated_cost": {
            "optimistic": {"amount": "number", "currency": "string"},
            "expected": {"amount": "number", "currency": "string"},
            "pessimistic": {"amount": "number", "currency": "string"},
        },
        "suggested_unit_price": {
            "amount": "number",
            "unit": "string",
            "currency": "string",
            "basis": "string — Explicación de cómo se calculó",
        },
        "suggested_breakdown": [
            {
                "name": "string",
                "days": "int",
                "unit_price": "number",
                "total": "number",
            }
        ],
        "suggested_technologies": ["string"],
        "notes": "string — Observaciones sobre la estimación",
    },
    indent=2,
    ensure_ascii=False,
)

MAX_PROMPT_TOKENS = 12000


def _format_scope_block(i: int, chunk: Any, currency: str) -> str:
    meta = chunk.metadata or {}
    content = (chunk.content_text or "")[:500]
    techs = ", ".join(chunk.technologies or []) or "No especificadas"
    related_items = meta.get("related_items", [])
    items_text = ""
    if related_items:
        items_text = "\nItems incluidos:\n" + "\n".join(
            f"  - {item}" if isinstance(item, str) else f"  - {item.get('name', str(item))}"
            for item in related_items
        )
    return (
        f"### Referencia {i} (similitud: {chunk.similarity_score:.2f}) — Bloque funcional\n"
        f"Proyecto: {chunk.project_title or 'N/A'}\n"
        f"Contenido: {content}\n"
        f"Coste total del bloque: {chunk.total_cost or 'N/A'} {currency}\n"
        f"Tecnologías: {techs}"
        f"{items_text}"
    )


def _format_line_item(i: int, chunk: Any, currency: str) -> str:
    meta = chunk.metadata or {}
    content = (chunk.content_text or "")[:300]
    return (
        f"### Referencia {i} (similitud: {chunk.similarity_score:.2f}) — Tarea individual\n"
        f"Proyecto: {chunk.project_title or 'N/A'}\n"
        f"Tarea: {meta.get('item_name', 'N/A')}\n"
        f"Descripción: {content}\n"
        f"Duración: {meta.get('quantity', 'N/A')} {meta.get('unit', 'N/A')}\n"
        f"Precio unitario: {meta.get('unit_price', 'N/A')} {currency}/{meta.get('unit', 'día')}\n"
        f"Total: {meta.get('total_price', 'N/A')} {currency}"
    )


def _format_phase(i: int, chunk: Any, currency: str) -> str:
    meta = chunk.metadata or {}
    deliverables = meta.get("deliverables", [])
    deliverables_text = ", ".join(deliverables) if isinstance(deliverables, list) else str(deliverables or "N/A")
    return (
        f"### Referencia {i} (similitud: {chunk.similarity_score:.2f}) — Fase de proyecto\n"
        f"Proyecto: {chunk.project_title or 'N/A'}\n"
        f"Fase: {meta.get('phase_name', 'N/A')}\n"
        f"Duración: {meta.get('duration', 'N/A')}\n"
        f"Coste total: {meta.get('phase_total_cost', 'N/A')} {currency}\n"
        f"Entregables: {deliverables_text}"
    )


def _format_project_overview(i: int, chunk: Any, currency: str) -> str:
    meta = chunk.metadata or {}
    content = (chunk.content_text or "")[:500]
    techs = ", ".join(chunk.technologies or []) or "No especificadas"
    return (
        f"### Referencia {i} (similitud: {chunk.similarity_score:.2f}) — Resumen de proyecto\n"
        f"Proyecto: {chunk.project_title or 'N/A'}\n"
        f"Contenido: {content}\n"
        f"Coste total: {chunk.total_cost or 'N/A'} {currency}\n"
        f"Tecnologías: {techs}"
    )


def _format_team_conditions(i: int, chunk: Any, currency: str) -> str:
    meta = chunk.metadata or {}
    content = (chunk.content_text or "")[:400]
    return (
        f"### Referencia {i} (similitud: {chunk.similarity_score:.2f}) — Condiciones de equipo\n"
        f"Proyecto: {chunk.project_title or 'N/A'}\n"
        f"Contenido: {content}\n"
        f"Dedicación: {meta.get('dedication', 'N/A')}\n"
        f"Condiciones de pago: {meta.get('payment_conditions', 'N/A')}"
    )


_FORMATTERS = {
    "scope_block": _format_scope_block,
    "line_item": _format_line_item,
    "phase": _format_phase,
    "project_overview": _format_project_overview,
    "team_conditions": _format_team_conditions,
}


def _format_chunk(i: int, chunk: Any, currency: str) -> str:
    formatter = _FORMATTERS.get(chunk.chunk_type, _format_project_overview)
    return formatter(i, chunk, currency)


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


def build_estimation_prompt(
    query: str,
    context: Any | None,
    chunks: list[Any],
    currency: str = "EUR",
) -> tuple[str, str, int]:
    """Build (system_prompt, user_prompt, chunks_used_count).

    Chunks are expected sorted by score descending (highest first).
    """
    # Sort by final_score or similarity_score descending
    sorted_chunks = sorted(
        chunks,
        key=lambda c: getattr(c, "final_score", c.similarity_score),
        reverse=True,
    )

    # Build context section
    if context is not None:
        project_type = getattr(context, "project_type", None) or "No especificado"
        techs_pref = getattr(context, "technologies_preferred", None)
        techs_str = ", ".join(techs_pref) if techs_pref else "No especificadas"
        team_size = getattr(context, "team_size", None) or "No especificado"
        complexity = getattr(context, "complexity", None) or "No especificada"
    else:
        project_type = "No especificado"
        techs_str = "No especificadas"
        team_size = "No especificado"
        complexity = "No especificada"

    context_section = (
        f"## Contexto del proyecto:\n"
        f"Tipo de proyecto: {project_type}\n"
        f"Tecnologías preferidas: {techs_str}\n"
        f"Tamaño del equipo: {team_size}\n"
        f"Complejidad percibida: {complexity}"
    )

    # Fixed parts (everything except the chunks section)
    prefix = (
        f"## Tarea a estimar:\n{query}\n\n"
        f"{context_section}\n\n"
    )
    suffix = (
        f"\n\n## Moneda para la estimación: {currency}\n\n"
        f"## Schema de respuesta JSON requerido:\n{RESPONSE_JSON_SCHEMA}"
    )

    fixed_overhead = _estimate_tokens(SYSTEM_PROMPT) + _estimate_tokens(prefix) + _estimate_tokens(suffix) + 50
    remaining_budget = MAX_PROMPT_TOKENS - fixed_overhead

    # Add chunks until budget exhausted
    used_chunks: list[Any] = []
    formatted_parts: list[str] = []
    token_count = 0

    for chunk in sorted_chunks:
        formatted = _format_chunk(len(used_chunks) + 1, chunk, currency)
        chunk_tokens = _estimate_tokens(formatted)
        if token_count + chunk_tokens > remaining_budget and used_chunks:
            break
        used_chunks.append(chunk)
        formatted_parts.append(formatted)
        token_count += chunk_tokens

    formatted_chunks = "\n\n".join(formatted_parts)
    chunks_header = f"## Datos históricos relevantes ({len(used_chunks)} referencias, ordenados por relevancia):\n\n"
    user_prompt = prefix + chunks_header + formatted_chunks + suffix

    return SYSTEM_PROMPT, user_prompt, len(used_chunks)
