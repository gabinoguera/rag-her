"""Prompts for the 3-step quote generation pipeline.

Step 1 (Analysis): Extracts structured requirements from a meeting transcription.
Step 3 (Generation): Produces a detailed QuoteOutput from the analysis + RAG context.
"""

from __future__ import annotations

from typing import Any

from app.core.prompt_builder import _format_chunk

# ---------------------------------------------------------------------------
# Step 1 — Analysis prompt (developer role for reasoning models)
# ---------------------------------------------------------------------------

ANALYSIS_PROMPT = """\
Eres un analista de requisitos senior con 15+ anos de experiencia en proyectos \
de software. Tu trabajo es analizar transcripciones de reuniones con clientes y \
extraer TODOS los requisitos del proyecto de forma estructurada.

REGLAS ESTRICTAS:
1. Extrae TODOS los modulos funcionales mencionados, sin omitir ninguno. \
Si se menciona una funcionalidad, debe aparecer como modulo o feature.
2. Identifica TODAS las integraciones con sistemas externos (pasarelas de pago, \
ERPs, CRMs, APIs de terceros, servicios de email, etc.).
3. Captura TODOS los tipos de usuario y roles de administracion mencionados.
4. Registra tanto las tecnologias mencionadas explicitamente como las que \
recomiendas basandote en los requisitos.
5. Identifica restricciones de plazo, presupuesto, legales o tecnicas.
6. Evalua la complejidad global: low (landing/web simple), medium (app con \
CRUD y 1-2 integraciones), high (plataforma con multiples modulos y \
integraciones), very_high (sistema enterprise con logica compleja).
7. Genera 3-5 queries de busqueda optimizadas para buscar presupuestos \
similares en una base de datos vectorial. Las queries deben ser especificas \
y focalizadas en los aspectos clave del proyecto (tipo de proyecto, \
funcionalidades principales, sector, tecnologias).
8. NO inventes requisitos que no se mencionen en la transcripcion. Si algo \
no se menciona explicitamente, no lo incluyas.
9. Si hay ambiguedades, registralas en constraints como "Pendiente de confirmar: ...".
10. Responde en espanol."""


ANALYSIS_USER_TEMPLATE = """\
Analiza la siguiente transcripcion de reunion con un cliente y extrae todos los \
requisitos del proyecto de forma estructurada.

{context_section}

## Transcripcion de la reunion:

{transcription}"""


# ---------------------------------------------------------------------------
# Step 3 — Generation prompt (developer role for reasoning models)
# ---------------------------------------------------------------------------

GENERATION_PROMPT = """\
Eres un arquitecto senior de proyectos de software con 15+ anos de experiencia \
creando presupuestos detallados. Tu trabajo es generar un presupuesto completo \
y desglosado basandote en el analisis de requisitos y datos historicos de \
proyectos similares.

REGLAS ESTRICTAS DE GRANULARIDAD:
1. MINIMO 3 scope_blocks (bloques funcionales), cada uno con al menos 3 features. \
Proyectos complejos deben tener 5-8 scope_blocks.
2. MINIMO 8 items (tareas desglosadas). Proyectos complejos deben tener 12-20 items.
3. MINIMO 3 roadmap_phases con duraciones realistas. Proyectos complejos: 4-6 fases.
4. Cada item debe tener una duracion realista en dias:
   - Tarea simple (configuracion, setup): 2-5 dias
   - Tarea media (modulo CRUD, integracion): 8-15 dias
   - Tarea compleja (motor de busqueda, checkout, panel admin): 15-30 dias
5. Los precios unitarios deben basarse en la MEDIANA de los datos historicos \
proporcionados. Si no hay datos suficientes, usa 350 EUR/dia como referencia.
6. Cada scope_block debe cubrir una area funcional distinta del proyecto.
7. Los items deben incluir SIEMPRE: analisis funcional, diseno UX/UI, QA/testing, \
y despliegue, ademas de las tareas de desarrollo.
8. Cada item debe estar asignado a una fase del roadmap via el campo 'phase'.
9. Las fases del roadmap deben seguir un orden logico: analisis -> diseno -> \
desarrollo core -> desarrollo secundario -> integraciones -> QA -> despliegue.
10. Todos los importes en la moneda especificada.

REGLAS DE COMPLETITUD:
- Si el analisis menciona un modulo funcional, DEBE haber un scope_block para el.
- Si el analisis menciona una integracion, DEBE haber al menos un item para ella.
- Los team_members deben reflejar los perfiles necesarios segun las tecnologias.
- Las conditions deben incluir condiciones de pago razonables (e.g. 30-40-30).

REGLAS SOBRE DATOS HISTORICOS:
- Usa los datos historicos como REFERENCIA para precios y duraciones.
- Si un proyecto historico similar tiene items con precios especificos, usarlos como guia.
- Si no hay datos historicos relevantes, estima basandote en la complejidad del analisis.
- Responde en espanol."""


GENERATION_USER_TEMPLATE = """\
Genera un presupuesto detallado y desglosado para el siguiente proyecto.

## Analisis de requisitos del proyecto:

**Proyecto:** {project_title}
**Descripcion:** {project_description}
**Complejidad estimada:** {estimated_complexity}

### Modulos funcionales identificados:
{modules_section}

### Integraciones:
{integrations_section}

### Tipos de usuario:
{user_types_section}

### Requisitos no funcionales:
{nfr_section}

### Tecnologias:
- Mencionadas: {technologies_mentioned}
- Recomendadas: {technologies_recommended}

### Restricciones:
{constraints_section}

{rag_section}

## Moneda: {currency}

{context_section}"""


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def build_analysis_user_prompt(
    transcription: str,
    context: Any | None = None,
) -> str:
    """Build the user prompt for Step 1 (transcription analysis)."""
    context_parts: list[str] = []
    if context is not None:
        if getattr(context, "client_name", None):
            context_parts.append(f"- Cliente: {context.client_name}")
        if getattr(context, "client_company", None):
            context_parts.append(f"- Empresa: {context.client_company}")
        if getattr(context, "technologies_preferred", None):
            techs = ", ".join(context.technologies_preferred)
            context_parts.append(f"- Tecnologias preferidas: {techs}")
        if getattr(context, "budget_hint", None):
            context_parts.append(f"- Presupuesto orientativo: {context.budget_hint} EUR")

    context_section = ""
    if context_parts:
        context_section = "## Contexto adicional:\n" + "\n".join(context_parts)

    return ANALYSIS_USER_TEMPLATE.format(
        context_section=context_section,
        transcription=transcription,
    )


def build_generation_user_prompt(
    analysis: Any,
    rag_chunks: list[Any],
    currency: str = "EUR",
    context: Any | None = None,
) -> str:
    """Build the user prompt for Step 3 (quote generation)."""
    # Format modules
    modules_lines: list[str] = []
    for mod in analysis.functional_modules:
        modules_lines.append(f"**{mod.title}**: {mod.description}")
        for feat in mod.features:
            modules_lines.append(f"  - {feat}")
    modules_section = "\n".join(modules_lines) if modules_lines else "No especificados"

    # Format integrations
    integrations_lines: list[str] = []
    for integ in (analysis.integrations or []):
        integrations_lines.append(
            f"- {integ.system}: {integ.purpose} (complejidad: {integ.complexity})"
        )
    integrations_section = (
        "\n".join(integrations_lines) if integrations_lines else "Ninguna identificada"
    )

    # Format user types
    user_types_lines: list[str] = []
    for ut in (analysis.user_types or []):
        user_types_lines.append(f"- {ut.name}: {ut.description}")
    user_types_section = (
        "\n".join(user_types_lines) if user_types_lines else "No especificados"
    )

    # Format NFRs
    nfr_section = (
        "\n".join(f"- {nfr}" for nfr in analysis.non_functional_requirements)
        if analysis.non_functional_requirements
        else "Ninguno especificado"
    )

    # Format technologies
    technologies_mentioned = (
        ", ".join(analysis.technologies_mentioned)
        if analysis.technologies_mentioned
        else "Ninguna"
    )
    technologies_recommended = (
        ", ".join(analysis.technologies_recommended)
        if analysis.technologies_recommended
        else "Ninguna"
    )

    # Format constraints
    constraints_section = (
        "\n".join(f"- {c}" for c in analysis.constraints)
        if analysis.constraints
        else "Ninguna identificada"
    )

    # Format RAG chunks
    if rag_chunks:
        formatted_parts: list[str] = []
        for i, chunk in enumerate(rag_chunks, 1):
            formatted_parts.append(_format_chunk(i, chunk, currency))
        rag_section = (
            f"## Datos historicos de proyectos similares "
            f"({len(rag_chunks)} referencias):\n\n"
            + "\n\n".join(formatted_parts)
        )
    else:
        rag_section = (
            "## Datos historicos:\nNo se encontraron proyectos similares en la "
            "base de datos. Estima basandote en la complejidad del analisis."
        )

    # Format optional context
    context_parts: list[str] = []
    if context is not None:
        if getattr(context, "team_size_hint", None):
            context_parts.append(f"- Tamano de equipo sugerido: {context.team_size_hint}")
        if getattr(context, "budget_hint", None):
            context_parts.append(f"- Presupuesto orientativo: {context.budget_hint} {currency}")
    context_section = (
        "## Contexto adicional:\n" + "\n".join(context_parts) if context_parts else ""
    )

    return GENERATION_USER_TEMPLATE.format(
        project_title=analysis.project_title,
        project_description=analysis.project_description,
        estimated_complexity=analysis.estimated_complexity,
        modules_section=modules_section,
        integrations_section=integrations_section,
        user_types_section=user_types_section,
        nfr_section=nfr_section,
        technologies_mentioned=technologies_mentioned,
        technologies_recommended=technologies_recommended,
        constraints_section=constraints_section,
        rag_section=rag_section,
        currency=currency,
        context_section=context_section,
    )
