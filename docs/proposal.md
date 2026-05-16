Contexto del Grupo Empresarial

AlmaWolf es un Venture Builder con presencia global (España, México, Kazajistán, Hong Kong, Marruecos, Argentina). Opera bajo un modelo de licencias y distribuye capital a través de sus empresas. La organización se estructura en tres unidades principales:

Unidad

Descripción

[CORP] AlmaWolf

Dirección estratégica, finanzas y administración del grupo

[SRV] Sagitaz

Servicios Zoho: consultoría e implementación. Pipeline: MKT → Ventas → Producción → Mantenimiento. Metodología DER/DERCAS, parametrización, documentación, migración, desarrollos Deluge, testeo, formación y soporte

[PROD] MCCP

Producto para Gobierno: motor de chatbot + automatizaciones de alta seguridad para licitaciones públicas

Woztell

Ofrece aplicativos para Whatsapp porque es proveedor oficial(solo hay 100 a nivel mundial). Principalmente ventas, marketing, etc.

Integraciones y Herramientas Actuales

Herramienta

Alcance y uso

Zoho (Transversal)

CRM, Calendar, Meet, Docs — ecosistema central para clientes privados. Incluye Zia Agents Studio, Catalyst, MCP para integración con modelos externos

WhatsApp API Oficial (Woztell)

Canal principal de comunicación; 125 números consolidados. Facturación: Meta + 10% AlmaWolf

Microsoft Teams

Reuniones internas y externas en Woztell

Notion

Transcripciones de reuniones y procesamiento previo al almacenamiento

Confluence / Jira

Documentación estructurada del programa CAIP, gestión de tareas y proyectos IA

Perplexity

Research y discovery previo a reuniones con clientes externos

Proyecto HER — Plan Maestro 2026

Última actualización: 11 de mayo de 2026  
Estado: Plan para PoC  
Responsable: Equipo IA Ops

Proyecto de inteligencia operacional conversacional para el grupo empresarial multi-sede (España, México, Kazajistán, Argentina, etc). Una app con agentes de IA tipo "Her"(en referencia a la pelicula) que conduce check-ins diarios con empleados y es capaz de asistir en la organización de tareas, ordenar prioridades, brindar información de utilidad(ejemplo: “Este cliente suena bien, pero ten en cuenta que es una entidad publica y que por mas de 60 mil euros caerás en una licitación”) y por otro lado genera síntesis consultable para dirección y un dashboard para management.

Objetivo 1: Resolver la falta de visibilidad operacional en tiempo real de toda la capa de Dirección sobre qué está haciendo cada persona en el grupo.

Objetivo 2: A la larga estaremos creando una entidad que domina el conocimiento del grupo tanto de los testimonios que se reportan, de los correos que se envian y llegan, de las reuniones que se agendaron, de los objetivos cumplidos, etc.

Dolores

Pains

Relatividad	

 Constancia	

 Idiomas	

 Uso horario	

 Cultura	

 Desinformación	

Solutions

Priorizacion

Determinismo

Multidiomas

Asincronia

Tropicalidad

Transferencia de informacion

Retos

Fricción

Adopción

Legales

Comodidad: device, momento

Utilidad para los actores

Conciliación

🎯 MoSCoW del Producto

MUST — Entregas Críticas (MVP)

Sin estos no hay producto:

Check-in conversacional diario (asistente pregunta, empleado habla)

Almacenamiento persistente de conversaciones

Consulta en lenguaje natural para capa dirección y capa empleado

Respuesta en voz

Que sea stateless

Con soporte para 80 usuarios simultáneos

Capa de managers (no solo CEO)

SHOULD — Completitud (Semana 8-10)

Hacen el producto usable:

Memoria entre sesiones (contexto histórico)

Conexto compartido entre usuarios de la misma empresa(solo managers?)

Síntesis por período (semana/mes)

Seguimiento de bloqueos activos

Soporte multiidioma (ES, EN)

COULD — Diferenciador (Fase 2)

Agregan potencia:

El asistente debe ser proactivo

Contraste con calendario/email (Zoho MCP)

Ordenamiento proactivo de tareas

Briefing automático semanal

Alertas por anomalías

Integración con PM tools

WON'T — Explícitamente Fuera de Alcance

Limites duros:

Scoring / evaluación de desempeño

No debe ser URL porque sino entran no soluciona el dolor(el canal se definirá)

Monitoreo en tiempo real

Asignación automática de tareas

Reemplazo de herramientas existentes

Acceso público/externo

Dashboard analitico o de reporte

🏗️ Arquitectura Conceptual

Tres Capas del Sistema

Capa 1 — Ingesta

Cómo entra la información al sistema:

Voz interfaz simple para PoC

Audio crudo de reuniones (no en base de datos)

Flujo: Audio → Whisper (STT) → Texto limpio → Embedding vectorial

Capa 2 — Memoria

Dónde guardamos qué aprendemos:

Memoria episódica: Chunks vectorizados de conversaciones (búsqueda semántica)

Memoria semántica: Hechos estructurados (objetivos, bloqueos, compromisos)

Memoria de contexto: Perfil de persona, empresa, sede

BD principal: Cloud SQL for PostgreSQL + pgvector

Capa 3 — Salida

Cómo entrega valor:

Síntesis en lenguaje natural (Gemini)

Respuesta en voz (TTS)

Consulta conversacional en voz/texto

Reporte de voz ondemand para dirección