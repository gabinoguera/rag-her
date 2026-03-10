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
8. NO inventes requisitos funcionales del negocio que no se mencionen en la \
transcripcion. Sin embargo, las fases estandar de todo proyecto de software \
profesional (exploracion/diseno, QA, despliegue) SIEMPRE deben incluirse \
como modulos funcionales, ya que son parte inherente de cualquier desarrollo.
9. SIEMPRE incluye como PRIMER modulo funcional uno de "Exploracion, Diseno y \
Definicion Funcional" que cubra: levantamiento detallado de requisitos, diseno UX/UI \
y prototipos, especificacion funcional completa, y definicion de arquitectura tecnica. \
Este modulo es estandar en todo proyecto de software profesional y no necesita ser \
mencionado explicitamente en la transcripcion.
10. Si hay ambiguedades, registralas en constraints como "Pendiente de confirmar: ...".
11. Responde en espanol.

FRAMEWORK DE DESCOMPOSICION (sigue este orden mental):
A. Identifica los TIPOS DE USUARIO y sus journeys principales.
B. Para cada journey, identifica los modulos funcionales que lo soportan.
C. Identifica las ENTIDADES DE DOMINIO clave y asignalas a modulos.
D. Identifica procesos BACKGROUND (tareas asincronas, notificaciones programadas, sincronizaciones).
E. Identifica INTEGRACIONES externas y si ameritan modulo propio o son features dentro de otro.
F. Identifica PREOCUPACIONES TRANSVERSALES (auth, notificaciones, auditoria, i18n, permisos).
G. Asegura que cada feature tiene descripcion concreta y esta vinculada a al menos un tipo de usuario.

REGLA DE GRANULARIDAD:
- Un modulo = un area funcional cohesiva, no una pantalla individual.
- Si tiene >8 features, considera dividirlo. Si tiene 1, fusionalo con otro.

REGLA DE QUERIES POR MODULO:
- search_query de cada modulo debe ser descriptiva, no solo el titulo.
  Ejemplo: "Motor de Reservas" -> "sistema de reservas online con calendario de disponibilidad en tiempo real y confirmacion automatica"."""


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
1. El numero minimo de scope_blocks depende de la complejidad del proyecto: \
low: MINIMO 4 scope_blocks, medium: MINIMO 5, high: MINIMO 6, very_high: MINIMO 7. \
Cada scope_block debe tener al menos 3 features. El primer scope_block siempre es \
el de exploracion y diseno.
2. El numero minimo de items depende de la complejidad: \
low: MINIMO 10 items, medium: MINIMO 12, high: MINIMO 15, very_high: MINIMO 20.
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
11. Elige un UNICO stack tecnologico coherente para todo el proyecto. No mezcles \
frameworks competidores (e.g., React y Vue, Django y FastAPI, Express y NestJS). \
Todos los scope_blocks deben usar tecnologias compatibles entre si.
12. Si el usuario especifica stack de frontend o backend en el contexto, es OBLIGATORIO \
usarlos. Los datos historicos sirven como referencia de costes y duraciones, \
NO como fuente de seleccion tecnologica.
13. Si no se especifican tecnologias, elige un stack coherente basandote en las \
tecnologias mencionadas o recomendadas en el analisis, y justifica la eleccion \
en las notas del presupuesto. Ten en cuenta que muchos proyectos usan el mismo \
stack para frontend y backend (e.g., Next.js full-stack, Nuxt full-stack, \
Django con templates, Rails con Hotwire) — esto es valido y a menudo preferible \
cuando el proyecto lo permite.
14. El PRIMER scope_block SIEMPRE debe ser "Exploracion, Diseno y Definicion Funcional" \
(o titulo equivalente). Este bloque cubre: descubrimiento del proyecto y levantamiento \
de requisitos, diseno UX/UI y prototipos, especificacion funcional detallada, y \
definicion de arquitectura tecnica. Es OBLIGATORIO en todos los proyectos, \
independientemente de su complejidad. Sus features deben incluir al menos: \
analisis de requisitos, wireframes/prototipos, documento de especificacion funcional, \
y diseno de arquitectura tecnica.

REGLAS DE COMPLETITUD:
- Si el analisis menciona un modulo funcional, DEBE haber un scope_block para el.
- Si el analisis menciona una integracion, DEBE haber al menos un item para ella.
- Los team_members deben reflejar los perfiles necesarios segun las tecnologias.
- Las conditions deben incluir condiciones de pago razonables (e.g. 30-40-30).

REGLAS SOBRE DATOS HISTORICOS:
- Usa los datos historicos como REFERENCIA para precios y duraciones.
- Si un proyecto historico similar tiene items con precios especificos, usarlos como guia.
- Si no hay datos historicos relevantes, estima basandote en la complejidad del analisis.

REGLAS DE USO DEL ANALISIS ENRIQUECIDO:
- Usa depends_on para ordenar fases del roadmap: modulos sin dependencias primero.
- La complexity por modulo influye en duracion: low: 2-8 dias, medium: 8-15, high: 15-30.
- key_entities indican complejidad del modelo de datos.
- cross_cutting_concerns deben traducirse en items concretos (auth -> items de auth, roles, permisos).
- Cada feature del analisis debe mapear a al menos un item en el presupuesto.

REGLAS DE MATCH CON DATOS HISTORICOS POR MODULO:
- Si una referencia historica coincide con un modulo especifico, usa sus costes como base.
- Si hay multiples referencias para el mismo tipo de modulo, usa la MEDIANA.

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

### Entidades de dominio:
{domain_entities_section}

### Preocupaciones transversales:
{cross_cutting_section}

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
    # Format modules with enriched info
    modules_lines: list[str] = []
    for i, mod in enumerate(analysis.functional_modules, 1):
        modules_lines.append(
            f"**{i}. {mod.title}** (complejidad: {mod.complexity}): {mod.description}"
        )
        if mod.depends_on:
            modules_lines.append(f"  Depende de: {', '.join(mod.depends_on)}")
        if mod.key_entities:
            modules_lines.append(f"  Entidades: {', '.join(mod.key_entities)}")
        for feat in mod.features:
            user_types_str = f" [{', '.join(feat.user_types)}]" if feat.user_types else ""
            modules_lines.append(f"  - {feat.name}: {feat.description}{user_types_str}")
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

    # Format domain entities
    domain_entities_lines: list[str] = []
    for entity in getattr(analysis, "domain_entities", None) or []:
        domain_entities_lines.append(f"- **{entity.name}**: {entity.description}")
    domain_entities_section = (
        "\n".join(domain_entities_lines) if domain_entities_lines else "No identificadas"
    )

    # Format cross-cutting concerns
    cross_cutting = getattr(analysis, "cross_cutting_concerns", None) or []
    cross_cutting_section = (
        "\n".join(f"- {c}" for c in cross_cutting)
        if cross_cutting
        else "Ninguna identificada"
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
        if getattr(context, "frontend_stack", None):
            context_parts.append(f"- Stack frontend REQUERIDO: {', '.join(context.frontend_stack)}")
        if getattr(context, "backend_stack", None):
            context_parts.append(f"- Stack backend REQUERIDO: {', '.join(context.backend_stack)}")
        if getattr(context, "technologies_preferred", None):
            context_parts.append(f"- Tecnologias preferidas adicionales: {', '.join(context.technologies_preferred)}")
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
        domain_entities_section=domain_entities_section,
        cross_cutting_section=cross_cutting_section,
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
