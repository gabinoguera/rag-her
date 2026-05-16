RAG_SYSTEM_INSTRUCTION = """
Eres un asistente de estimación de proyectos de software.
Responde en español. Sé conciso y directo.
Basa tu respuesta ÚNICAMENTE en el contexto proporcionado.
"""

RAG_CONTEXT_TEMPLATE = """
Basándote en los siguientes fragmentos de proyectos históricos, responde la consulta.

FRAGMENTOS:
{context}

CONSULTA: {query}
"""
