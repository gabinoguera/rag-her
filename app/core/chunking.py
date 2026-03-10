from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from app.api.schemas.quote_input import ItemInput, QuoteInput, RoadmapPhaseInput, ScopeBlockInput
from app.utils.text_processing import parse_duration_weeks

# ~8000 tokens at ~3.5 chars/token ratio — safety net before embedding truncation
MAX_CHUNK_CHARS = 28000


@dataclass
class ChunkData:
    """Intermediate representation of a chunk before persistence."""

    chunk_type: str
    content_text: str
    metadata: dict
    project_title: str
    technologies: list[str] = field(default_factory=list)
    total_cost: Decimal | None = None
    currency: str | None = None


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _calculate_total_budget(items: list[ItemInput]) -> Decimal:
    return sum(
        (Decimal(str(item.quantity)) * Decimal(str(item.unit_price)) for item in items),
        Decimal("0"),
    )


def _aggregate_technologies(scope_blocks: list[ScopeBlockInput]) -> list[str]:
    """Collect and deduplicate technologies across scope blocks, preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for sb in scope_blocks:
        for tech in sb.technologies or []:
            if tech not in seen:
                seen.add(tech)
                result.append(tech)
    return result


def _calculate_total_duration(phases: list[RoadmapPhaseInput]) -> int:
    total = 0
    for phase in phases:
        if phase.duration:
            weeks = parse_duration_weeks(phase.duration)
            if weeks is not None:
                total += weeks
    return total


def _tokenize(text: str) -> set[str]:
    """Simple whitespace/punctuation tokenizer for keyword matching."""
    return {w.lower().strip(".,;:()[]{}\"'") for w in text.split() if len(w) > 2}


def _link_items_to_scope_blocks(
    scope_blocks: list[ScopeBlockInput],
    items: list[ItemInput],
    phases: list[RoadmapPhaseInput],
) -> dict[str, list[ItemInput]]:
    """Link items to scope blocks using phase-module matching and keyword matching.

    Returns a dict mapping scope_block.title -> list of linked items.
    """
    result: dict[str, list[ItemInput]] = {sb.title: [] for sb in scope_blocks}
    linked_items: set[int] = set()  # indices of items already linked

    # Step 1: Phase-module matching
    # For each scope block, find phases whose modules contain the scope block title
    # Then find items whose phase matches those phase names
    for sb in scope_blocks:
        sb_title_lower = sb.title.lower()
        matching_phase_names: set[str] = set()
        for phase in phases:
            if phase.modules:
                for module in phase.modules:
                    if sb_title_lower in module.lower() or module.lower() in sb_title_lower:
                        matching_phase_names.add(phase.name)
                        break

        for i, item in enumerate(items):
            if i not in linked_items and item.phase and item.phase in matching_phase_names:
                result[sb.title].append(item)
                linked_items.add(i)

    # Step 2: Keyword matching for unlinked items
    for i, item in enumerate(items):
        if i in linked_items:
            continue

        item_tokens = _tokenize(item.name)
        if item.description:
            item_tokens |= _tokenize(item.description)

        best_sb: str | None = None
        best_score = 0

        for sb in scope_blocks:
            sb_tokens = _tokenize(sb.title)
            for feature in sb.features or []:
                sb_tokens |= _tokenize(feature)
            if sb.detailed_features:
                for df in sb.detailed_features:
                    sb_tokens |= _tokenize(df.title)

            overlap = len(item_tokens & sb_tokens)
            if overlap > best_score:
                best_score = overlap
                best_sb = sb.title

        if best_sb is not None and best_score >= 1:
            result[best_sb].append(item)
            linked_items.add(i)

    return result


# ---------------------------------------------------------------------------
# Chunk builders
# ---------------------------------------------------------------------------


def _build_project_overview_chunk(
    quote: QuoteInput,
    document_id: UUID,
    total_budget: Decimal,
    all_technologies: list[str],
    total_duration: int,
) -> ChunkData:
    project_title = quote.project.title if quote.project else "Sin titulo"
    subtitle = quote.project.subtitle if quote.project else None

    lines: list[str] = []
    lines.append(f"Proyecto: {project_title}")
    if subtitle:
        lines.append(f"Descripcion: {subtitle}")

    if quote.objectives:
        lines.append("Objetivos del proyecto:")
        for obj in quote.objectives:
            desc = f" - {obj.description}" if obj.description else ""
            lines.append(f"- {obj.title}{desc}")

    if all_technologies:
        lines.append(f"Tecnologias principales: {', '.join(all_technologies)}")

    if total_duration > 0:
        lines.append(f"Duracion total: {total_duration} semanas")

    if quote.team_members:
        team_parts: list[str] = []
        for tm in quote.team_members:
            ded = "tiempo completo" if tm.dedication == "full_time" else "tiempo parcial"
            team_parts.append(f"{tm.profile_type} x{tm.quantity} ({ded})")
        lines.append(f"Equipo: {', '.join(team_parts)}")

    lines.append(f"Presupuesto total: {total_budget} {quote.currency}")

    team_size = sum(m.quantity for m in (quote.team_members or []))

    return ChunkData(
        chunk_type="project_overview",
        content_text="\n".join(lines),
        metadata={
            "chunk_type": "project_overview",
            "project_title": project_title,
            "total_budget": float(total_budget),
            "currency": quote.currency,
            "total_duration_weeks": total_duration,
            "team_size": team_size,
            "technologies": all_technologies,
            "scope_blocks_count": len(quote.scope_blocks),
            "items_count": len(quote.items),
            "phases_count": len(quote.roadmap_phases or []),
            "source_quote_id": str(document_id),
        },
        project_title=project_title,
        technologies=all_technologies,
        total_cost=total_budget,
        currency=quote.currency,
    )


def _build_scope_block_chunks(
    quote: QuoteInput,
    document_id: UUID,
    scope_items_map: dict[str, list[ItemInput]],
) -> list[ChunkData]:
    project_title = quote.project.title if quote.project else "Sin titulo"
    chunks: list[ChunkData] = []

    for sb in quote.scope_blocks:
        lines: list[str] = []
        lines.append(f"Bloque funcional: {sb.title}")
        lines.append(f"Resumen: {sb.short_description}")
        if sb.long_description:
            lines.append(f"Descripcion completa: {sb.long_description}")

        if sb.features:
            lines.append("Funcionalidades:")
            for feat in sb.features:
                lines.append(f"- {feat}")

        if sb.technologies:
            lines.append(f"Tecnologias: {', '.join(sb.technologies)}")

        if sb.detailed_features:
            lines.append("Funcionalidades detalladas:")
            for df in sb.detailed_features:
                desc = f": {df.description}" if df.description else ""
                lines.append(f"- {df.title}{desc}")

        # Linked items
        linked_items = scope_items_map.get(sb.title, [])
        related_items_meta: list[dict] = []
        block_total = Decimal("0")

        if linked_items:
            lines.append("Items incluidos:")
            for item in linked_items:
                item_total = Decimal(str(item.quantity)) * Decimal(str(item.unit_price))
                block_total += item_total
                lines.append(
                    f"- {item.name}: {item.quantity} {item.unit} x "
                    f"{item.unit_price} {quote.currency} = {item_total} {quote.currency}"
                )
                related_items_meta.append({
                    "name": item.name,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "unit_price": item.unit_price,
                    "total": float(item_total),
                })

            lines.append(f"Coste total del bloque: {block_total} {quote.currency}")

        chunks.append(ChunkData(
            chunk_type="scope_block",
            content_text="\n".join(lines),
            metadata={
                "chunk_type": "scope_block",
                "block_title": sb.title,
                "technologies": sb.technologies or [],
                "features": sb.features or [],
                "project_title": project_title,
                "source_quote_id": str(document_id),
                "related_items": related_items_meta,
                "block_total_cost": float(block_total),
                "currency": quote.currency,
            },
            project_title=project_title,
            technologies=sb.technologies or [],
            total_cost=block_total if block_total > 0 else None,
            currency=quote.currency,
        ))

    return chunks


def _build_line_item_chunks(
    quote: QuoteInput,
    document_id: UUID,
) -> list[ChunkData]:
    project_title = quote.project.title if quote.project else "Sin titulo"
    chunks: list[ChunkData] = []

    for item in quote.items:
        item_total = Decimal(str(item.quantity)) * Decimal(str(item.unit_price))

        lines: list[str] = []
        lines.append(f"Tarea: {item.name}")
        if item.description:
            lines.append(f"Descripcion: {item.description}")
        lines.append(f"Tipo: {item.type}")
        lines.append(
            f"Estimacion: {item.quantity} {item.unit} a "
            f"{item.unit_price} {quote.currency}/{item.unit}"
        )
        lines.append(f"Total: {item_total} {quote.currency}")
        if item.phase:
            lines.append(f"Fase: {item.phase}")

        chunks.append(ChunkData(
            chunk_type="line_item",
            content_text="\n".join(lines),
            metadata={
                "chunk_type": "line_item",
                "item_name": item.name,
                "item_type": item.type,
                "quantity": item.quantity,
                "unit": item.unit,
                "unit_price": item.unit_price,
                "total_price": float(item_total),
                "discount_percent": item.discount_percent,
                "currency": quote.currency,
                "phase": item.phase,
                "project_title": project_title,
                "source_quote_id": str(document_id),
            },
            project_title=project_title,
            technologies=[],
            total_cost=item_total,
            currency=quote.currency,
        ))

    return chunks


def _build_phase_chunks(
    quote: QuoteInput,
    document_id: UUID,
) -> list[ChunkData]:
    if not quote.roadmap_phases:
        return []

    project_title = quote.project.title if quote.project else "Sin titulo"
    chunks: list[ChunkData] = []

    for phase in quote.roadmap_phases:
        # Filter items belonging to this phase
        phase_items = [item for item in quote.items if item.phase == phase.name]
        phase_total = sum(
            (Decimal(str(i.quantity)) * Decimal(str(i.unit_price)) for i in phase_items),
            Decimal("0"),
        )
        duration_weeks = parse_duration_weeks(phase.duration) if phase.duration else None

        lines: list[str] = []
        lines.append(f"Fase: {phase.name}")
        if phase.duration:
            lines.append(f"Duracion: {phase.duration}")
        if phase.description:
            lines.append(f"Descripcion: {phase.description}")

        if phase.deliverables:
            lines.append("Entregables:")
            for d in phase.deliverables:
                lines.append(f"- {d}")

        if phase.modules:
            lines.append(f"Modulos involucrados: {', '.join(phase.modules)}")

        if phase_items:
            lines.append("Tareas incluidas:")
            for item in phase_items:
                item_total = Decimal(str(item.quantity)) * Decimal(str(item.unit_price))
                lines.append(f"- {item.name}: {item_total} {quote.currency}")
            lines.append(f"Coste total de la fase: {phase_total} {quote.currency}")

        chunks.append(ChunkData(
            chunk_type="phase",
            content_text="\n".join(lines),
            metadata={
                "chunk_type": "phase",
                "phase_name": phase.name,
                "duration": phase.duration,
                "duration_weeks": duration_weeks,
                "deliverables": phase.deliverables or [],
                "modules": phase.modules or [],
                "phase_total_cost": float(phase_total),
                "items_count": len(phase_items),
                "currency": quote.currency,
                "project_title": project_title,
                "source_quote_id": str(document_id),
            },
            project_title=project_title,
            technologies=[],
            total_cost=phase_total if phase_total > 0 else None,
            currency=quote.currency,
        ))

    return chunks


def _build_team_conditions_chunk(
    quote: QuoteInput,
    document_id: UUID,
    total_budget: Decimal,
) -> ChunkData | None:
    if not quote.team_members and not quote.conditions:
        return None

    project_title = quote.project.title if quote.project else "Sin titulo"
    lines: list[str] = []
    team_composition: list[dict] = []
    total_team_size = 0

    if quote.team_members:
        lines.append("Equipo del proyecto:")
        for tm in quote.team_members:
            ded = "tiempo completo" if tm.dedication == "full_time" else "tiempo parcial"
            desc = f", {tm.description}" if tm.description else ""
            lines.append(
                f"- {tm.profile_type}: {tm.quantity} persona(s), dedicacion {ded}{desc}"
            )
            team_composition.append({
                "profile": tm.profile_type,
                "quantity": tm.quantity,
                "dedication": tm.dedication,
            })
            total_team_size += tm.quantity

    if quote.conditions:
        if quote.conditions.payment_terms:
            lines.append("")
            lines.append("Condiciones de pago:")
            for pt in quote.conditions.payment_terms:
                lines.append(f"- {pt}")

        if quote.conditions.included_services:
            lines.append("")
            lines.append("Servicios incluidos:")
            for svc in quote.conditions.included_services:
                lines.append(f"- {svc}")

        if quote.conditions.additional_services:
            lines.append("")
            lines.append("Servicios adicionales:")
            for asvc in quote.conditions.additional_services:
                lines.append(f"- {asvc.name}: {asvc.price} {quote.currency}")

    payment_milestones = (
        len(quote.conditions.payment_terms)
        if quote.conditions and quote.conditions.payment_terms
        else 0
    )

    return ChunkData(
        chunk_type="team_conditions",
        content_text="\n".join(lines),
        metadata={
            "chunk_type": "team_conditions",
            "team_composition": team_composition,
            "total_team_size": total_team_size,
            "payment_milestones": payment_milestones,
            "project_title": project_title,
            "total_budget": float(total_budget),
            "currency": quote.currency,
            "source_quote_id": str(document_id),
        },
        project_title=project_title,
        technologies=[],
        total_cost=total_budget,
        currency=quote.currency,
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def generate_chunks(quote: QuoteInput, document_id: UUID) -> list[ChunkData]:
    """Generate all chunks from a validated and anonymized quote.

    Returns a list of ChunkData objects ready for embedding and storage.
    """
    all_technologies = _aggregate_technologies(quote.scope_blocks)
    total_budget = _calculate_total_budget(quote.items)
    total_duration = _calculate_total_duration(quote.roadmap_phases or [])
    scope_items_map = _link_items_to_scope_blocks(
        quote.scope_blocks, quote.items, quote.roadmap_phases or []
    )

    chunks: list[ChunkData] = []

    # 1. Project overview (1)
    chunks.append(
        _build_project_overview_chunk(
            quote, document_id, total_budget, all_technologies, total_duration
        )
    )

    # 2. Scope blocks (N)
    chunks.extend(_build_scope_block_chunks(quote, document_id, scope_items_map))

    # 3. Line items (N)
    chunks.extend(_build_line_item_chunks(quote, document_id))

    # 4. Phases (N)
    chunks.extend(_build_phase_chunks(quote, document_id))

    # 5. Team & conditions (0 or 1)
    team_chunk = _build_team_conditions_chunk(quote, document_id, total_budget)
    if team_chunk is not None:
        chunks.append(team_chunk)

    # Truncate chunks that exceed the character safety limit
    for chunk in chunks:
        if len(chunk.content_text) > MAX_CHUNK_CHARS:
            chunk.content_text = chunk.content_text[:MAX_CHUNK_CHARS]

    return chunks
