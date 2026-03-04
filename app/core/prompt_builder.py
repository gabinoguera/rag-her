from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT = """\
Eres un experto en estimación de proyectos de software con más de 15 años de \
experiencia. Tu trabajo es generar estimaciones de esfuerzo basándote \
en datos históricos de presupuestos reales proporcionados como contexto.

REGLAS ESTRICTAS:
1. Basa tus estimaciones EXCLUSIVAMENTE en los datos proporcionados como contexto. \
No inventes datos ni uses conocimiento externo sobre precios.
2. Proporciona siempre tres escenarios: optimista, esperado y pesimista.
3. El escenario optimista debe ser estrictamente menor que el esperado, \
y el esperado estrictamente menor que el pesimista.
4. Desglosa la estimación en bloques funcionales con tareas granulares.
5. Si los datos históricos son insuficientes (menos de 2 referencias relevantes), \
indica explícitamente que la confianza es baja.
6. Responde ÚNICAMENTE con un JSON válido siguiendo el schema proporcionado. \
Sin texto adicional, sin markdown, sin explicaciones fuera del JSON.
7. Las horas estimadas deben ser números enteros.
8. Si las referencias históricas usan unidades distintas a horas, \
normaliza todo a horas (1 día = 8 horas).
9. Cada bloque funcional en suggested_breakdown debe tener entre 3 y 8 tareas \
granulares que desglosen el trabajo necesario. Los nombres de las tareas deben \
ser distintos al nombre del bloque y describir acciones concretas."""

RESPONSE_JSON_SCHEMA = json.dumps(
    {
        "summary": "string — Resumen en 1-2 frases de la estimación",
        "estimated_effort": {
            "optimistic": {"hours": "int"},
            "expected": {"hours": "int"},
            "pessimistic": {"hours": "int"},
        },
        "suggested_breakdown": [
            {
                "name": "string — Nombre del bloque funcional",
                "tasks": [
                    {
                        "name": "string — Nombre de la tarea granular",
                        "hours": "int",
                    }
                ],
            }
        ],
        "suggested_technologies": ["string"],
        "notes": "string — Observaciones sobre la estimación",
    },
    indent=2,
    ensure_ascii=False,
)

MAX_PROMPT_TOKENS = 12000

VALIDATION_SYSTEM_PROMPT = """\
Eres un experto en estimación de proyectos de software. Tu tarea es VALIDAR y AJUSTAR \
una estimación existente utilizando datos históricos específicos para cada tarea.

REGLAS ESTRICTAS:
1. Para cada tarea, compara las horas propuestas con los datos históricos proporcionados.
2. Si los datos históricos sugieren un rango diferente, ajusta las horas y explica por qué.
3. Si no hay datos históricos para una tarea, mantén las horas originales y marca \
"Sin referencia histórica" como razón.
4. Las horas totales (optimistic/expected/pessimistic) deben recalcularse como la suma \
de las horas validadas de todas las tareas.
5. Mantén la relación: optimistic < expected < pessimistic.
6. Responde ÚNICAMENTE con un JSON válido siguiendo el schema proporcionado.
7. Las horas deben ser números enteros."""

VALIDATION_JSON_SCHEMA = json.dumps(
    {
        "validated_breakdown": [
            {
                "name": "string — Nombre del bloque funcional",
                "tasks": [
                    {
                        "name": "string — Nombre de la tarea",
                        "original_hours": "int — Horas originales propuestas",
                        "validated_hours": "int — Horas tras validación",
                        "adjustment_reason": "string | null — Razón del ajuste",
                        "references_found": "int — Número de referencias históricas",
                    }
                ],
            }
        ],
        "estimated_effort": {
            "optimistic": {"hours": "int"},
            "expected": {"hours": "int"},
            "pessimistic": {"hours": "int"},
        },
        "adjustment_notes": "string — Resumen de los ajustes realizados",
    },
    indent=2,
    ensure_ascii=False,
)


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


def build_validation_prompt(
    original_breakdown: list[Any],
    task_references: list[Any],
    original_effort: dict,
    currency: str = "EUR",
) -> tuple[str, str]:
    """Build (system_prompt, user_prompt) for the validation pass."""
    ref_lookup: dict[tuple[str, str], Any] = {
        (r.block_name, r.task_name): r for r in task_references
    }

    sections: list[str] = []
    sections.append("## Estimación original a validar:\n")

    for block in original_breakdown:
        block_name = block.name if hasattr(block, "name") else block["name"]
        tasks = block.tasks if hasattr(block, "tasks") else block["tasks"]
        sections.append(f"### Bloque: {block_name}")

        for task in tasks:
            task_name = task.name if hasattr(task, "name") else task["name"]
            task_hours = task.hours if hasattr(task, "hours") else task["hours"]
            sections.append(f"  - Tarea: {task_name} — {task_hours} horas propuestas")

            ref = ref_lookup.get((block_name, task_name))
            if ref and ref.historical_hours:
                avg_h = sum(ref.historical_hours) / len(ref.historical_hours)
                min_h = min(ref.historical_hours)
                max_h = max(ref.historical_hours)
                sections.append(
                    f"    Datos históricos ({len(ref.historical_hours)} referencias, "
                    f"similitud promedio: {ref.avg_similarity:.2f}):"
                )
                sections.append(
                    f"    - Rango: {min_h:.0f}h - {max_h:.0f}h, "
                    f"Promedio: {avg_h:.0f}h"
                )
                for i, chunk in enumerate(ref.chunks[:3], 1):
                    meta = chunk.metadata or {} if hasattr(chunk, "metadata") else {}
                    sections.append(
                        f"    Ref {i}: {meta.get('item_name', 'N/A')} — "
                        f"{meta.get('quantity', '?')} {meta.get('unit', '?')} "
                        f"(sim: {chunk.similarity_score:.2f})"
                    )
            else:
                sections.append("    Sin datos históricos específicos para esta tarea.")

    opt = original_effort.get("optimistic", {})
    exp = original_effort.get("expected", {})
    pes = original_effort.get("pessimistic", {})
    opt_h = opt.get("hours", opt.hours) if hasattr(opt, "hours") else opt.get("hours", "?")
    exp_h = exp.get("hours", exp.hours) if hasattr(exp, "hours") else exp.get("hours", "?")
    pes_h = pes.get("hours", pes.hours) if hasattr(pes, "hours") else pes.get("hours", "?")

    sections.append(f"\n## Esfuerzo original:")
    sections.append(f"  Optimista: {opt_h}h")
    sections.append(f"  Esperado: {exp_h}h")
    sections.append(f"  Pesimista: {pes_h}h")

    sections.append(f"\n## Moneda: {currency}")
    sections.append(f"\n## Schema de respuesta JSON requerido:\n{VALIDATION_JSON_SCHEMA}")

    user_prompt = "\n".join(sections)
    return VALIDATION_SYSTEM_PROMPT, user_prompt
