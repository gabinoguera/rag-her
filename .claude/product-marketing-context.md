# Product Marketing Context — Archivo Final

*Last updated: 2026-02-25*

## Product Overview
**One-liner:** Plataforma de evaluación literaria profesional que genera informes de lectura mediante IA y conecta autores con editoriales.
**What it does:** Archivo Final analiza manuscritos de ficción narrativa con inteligencia artificial (Google Gemini) y genera un informe de lectura profesional con 8 secciones: sinopsis, clasificación de género (THEMA v1.6), personajes, fluidez, coherencia, calidad del texto, originalidad y adaptabilidad multiplataforma. Los manuscritos que superan el umbral de calidad (7/10 en todas las métricas) reciben matching automático con editoriales afines.
**Product category:** Plataforma de evaluación literaria / Literary analytics
**Product type:** SaaS (web app)
**Business model:** Freemium — 3 informes gratuitos por usuario. Premium en desarrollo.

### Platforms
| Platform | URL | Stack | Purpose |
|----------|-----|-------|---------|
| Commercial site | archivofinal.com | WordPress + Astra | Marketing, blog, lead capture |
| Web app | app.archivofinal.com | Django 4.2 | Upload, reports, profiles, matching |

### WordPress Site Structure
- **Inicio** (archivofinal.com) — Hero + 3 pilares (Informe, Propuesta, Match) + Cómo funciona
- **Leo** (archivofinal.com/leo/) — Producto: informe de lectura inteligente
- **Sobre nosotros** — Historia fundacional, equipo
- **Actualidad** — Blog con artículos sobre escritura, IA y sector editorial
- **Contacto** ("Hablemos") — Formulario de contacto

### Current Hero Copy (WordPress)
- Headline: "Todo comienza con un manuscrito"
- Subheadline: "Descubre el potencial de tu manuscrito y conecta con las editoriales adecuadas"
- Primary CTA: "Subir Manuscrito" → app.archivofinal.com
- Secondary: "Cómo funciona" → anchor

### Three Value Pillars (WordPress)
1. **Informe** — "Una lectura técnica y objetiva que revela el potencial editorial de tu manuscrito"
2. **Propuesta** — "Presentar tu obra como lo hacen los profesionales: con un briefing y una carta editorial"
3. **Match** — "Conectar con las editoriales que buscan historias como la tuya"

### Contact
- Email: hola@archivofinal.com
- Phone: 744610517
- Address: Calle Alboraya 10, puerta 3, Valencia 46010, Spain

## Target Audience

### Side A — Escritores (B2C)
**Target:** Autores de ficción narrativa en español — desde escritores emergentes hasta autores con obra terminada buscando editorial.
**Primary use case:** Obtener una evaluación profesional objetiva de su manuscrito antes de enviarlo a editoriales.
**Jobs to be done:**
- Saber si mi manuscrito está listo para enviar a editoriales
- Obtener feedback profesional y detallado sobre mi obra
- Descubrir qué editoriales encajan con mi estilo y género
- Construir un perfil profesional de autor verificado

### Side B — Profesionales Editoriales (B2B)
**Target:** Editores, agentes literarios, scouts de editoriales que buscan descubrir talento.
**Primary use case:** Acceder a un catálogo filtrado de escritores con manuscritos pre-evaluados y cualificados.
**Jobs to be done:**
- Descubrir autores con manuscritos de calidad verificada
- Reducir el tiempo de criba de manuscritos no solicitados
- Acceder a perfiles profesionales de escritores validados

## Personas

| Persona | Cares about | Challenge | Value we promise |
|---------|-------------|-----------|------------------|
| Escritor emergente | Saber si su obra tiene calidad profesional | No tiene acceso a lectores profesionales ni feedback honesto | Evaluación objetiva y profesional sin necesidad de contactos en el sector |
| Escritor con obra terminada | Encontrar editorial adecuada | Enviar manuscritos a ciegas, no saber qué editorial encaja | Matching inteligente con editoriales afines a su género y estilo |
| Editor / Agente literario | Descubrir talento de calidad | Volumen abrumador de manuscritos no solicitados | Catálogo filtrado de autores con calidad verificada por IA |

## Problems & Pain Points

**Core problem — Escritores:**
El proceso editorial es opaco. Los autores terminan un manuscrito y no tienen forma objetiva de saber si tiene calidad profesional. Envían a ciegas a editoriales, reciben rechazos sin feedback, y no saben qué mejorar ni a quién dirigirse.

**Core problem — Editoriales:**
Reciben cientos de manuscritos no solicitados. La criba es costosa en tiempo y recursos. Se pierden buenos manuscritos en la avalancha.

**Why alternatives fall short:**
- Lectores beta: subjetivos, no profesionales, lenta respuesta
- Servicios de lectura editorial: caros (150-500€), semanas de espera, una sola opinión
- Envío directo a editoriales: rechazo sin feedback, proceso ciego
- Autoedición: sin filtro de calidad, sin acceso al sector editorial

**What it costs them:**
- Meses o años de espera sin feedback
- Dinero en servicios de lectura profesional (150-500€ por informe)
- Oportunidades perdidas por enviar a editoriales equivocadas
- Frustración y abandono de la escritura

**Emotional tension:** Inseguridad sobre la calidad de su trabajo. Sensación de que el mundo editorial es un club cerrado. Miedo a que su historia nunca sea leída.

## Competitive Landscape

**Direct competitors:** Servicios de lectura profesional (lectores editoriales freelance, agencias de lectura)
— Caros (150-500€), lentos (semanas), una sola opinión subjetiva

**Secondary competitors:** Plataformas de escritura (Wattpad, Lektu, Amazon KDP)
— Orientadas a publicación/distribución, no a evaluación profesional

**Indirect competitors:** Beta readers, talleres literarios, premios literarios
— No ofrecen evaluación estructurada ni conexión con editoriales

## Differentiation

**Key differentiators:**
- Evaluación con IA de nivel profesional a coste cero (freemium)
- 8 métricas objetivas y comparables (no solo una opinión)
- Clasificación con estándar THEMA v1.6 (el mismo que usan las editoriales)
- Matching automático con editoriales basado en género y calidad
- Resultado en minutos, no semanas
- Perfil profesional verificado para autores cualificados
- Catálogo de escritores filtrado para profesionales editoriales

**How we do it differently:** Combinamos IA (Google Gemini enterprise) con estándares editoriales profesionales (THEMA v1.6) para ofrecer evaluaciones objetivas, rápidas y accesibles.

**Why customers choose us:** Rapidez, objetividad, accesibilidad económica, y la posibilidad real de conectar con editoriales.

## Objections & Responses

| Objection | Response |
|-----------|----------|
| "Una IA no puede evaluar literatura" | Usamos Google Gemini con prompts diseñados por profesionales editoriales. La IA evalúa estructura, coherencia, calidad técnica — aspectos medibles. No sustituye al criterio editorial humano, lo complementa. |
| "¿Y la privacidad de mi manuscrito?" | Los manuscritos se procesan con Vertex AI enterprise (no se usan para entrenar modelos). Los PDFs se eliminan automáticamente tras el análisis. Tus derechos de propiedad intelectual son siempre tuyos. Servidores en Europa (GDPR). |
| "¿Es fiable un informe gratuito?" | El modelo freemium nos permite democratizar el acceso a la evaluación profesional. La calidad del informe es la misma que en premium. |
| "Solo evalúa ficción narrativa" | Estamos ampliando géneros progresivamente. La ficción narrativa es nuestro punto fuerte y donde la IA ofrece mayor valor. |

**Anti-persona:** Autores que buscan solo validación emocional (no feedback objetivo). Escritores de no-ficción, poesía o formatos no narrativos (por ahora).

## Switching Dynamics (JTBD Four Forces)

**Push:** Frustración con el proceso opaco de envío a editoriales. Coste y tiempo de lectores profesionales.
**Pull:** Evaluación instantánea, gratuita, profesional. Posibilidad real de matching con editoriales.
**Habit:** "Siempre he enviado directamente a editoriales" / "Mi grupo de escritura me da feedback"
**Anxiety:** "¿Puede una IA entender mi obra?" / "¿Qué pasa con la privacidad de mi manuscrito?"

## Customer Language

**How they describe the problem:**
- "No sé si mi novela está lista para enviar a editoriales"
- "He terminado mi manuscrito y no sé qué hacer ahora"
- "Los lectores profesionales son carísimos"
- "Envío a editoriales y nunca me responden"
- "No sé a qué editorial mandar mi libro"

**How they describe us:**
- "Un lector profesional con IA"
- "Me dice si mi manuscrito tiene nivel editorial"
- "Te conecta con editoriales que encajan con tu libro"

**Words to use:** manuscrito, obra, informe de lectura, evaluación, autor/a, editorial, publicación, género literario, calidad narrativa, feedback profesional
**Words to avoid:** algoritmo, machine learning, pipeline, procesamiento, motor de IA, disrupción, revolucionar, transformar (demasiado tech/startup)

**Glossary:**
| Term | Meaning |
|------|---------|
| Informe de lectura | Evaluación profesional estructurada de un manuscrito |
| THEMA | Estándar internacional de clasificación de géneros editoriales (v1.6) |
| Manuscrito cualificado | Manuscrito con puntuación >= 7 en todas las métricas |
| Matching editorial | Emparejamiento automático entre manuscrito y editoriales afines |
| Perfil verificado | Perfil de autor revisado y aprobado por el equipo de Archivo Final |

## Brand Voice

**Tone:** Profesional pero cercano. Culto sin ser académico. Cálido sin ser informal.
**Style:** Directo, claro, con sensibilidad literaria. Usa el "tú" pero con respeto. Evita jerga tech.
**Personality:** Cercano, profesional, apasionado por la literatura, honesto, accesible.
**Language:** Español (España). Puede incluir términos editoriales en inglés cuando son estándar del sector (pitch, feedback, etc.)

## Proof Points

**Metrics:**
- 8 métricas de evaluación profesional
- Clasificación con estándar THEMA v1.6 (161 géneros)
- Resultado en minutos (vs semanas con lectores humanos)
- 3 informes gratuitos por usuario

**Technology credibility:**
- Google Gemini via Vertex AI (enterprise-grade)
- Servidores en Europa (europe-west1, GDPR)
- PDFs auto-eliminados tras análisis
- Prompts diseñados por profesionales editoriales

**Testimonials:** (pendiente de recopilar)

**Value themes:**
| Theme | Proof |
|-------|-------|
| Accesibilidad | 3 informes gratuitos, resultado en minutos |
| Profesionalidad | 8 métricas, estándar THEMA v1.6, prompts editoriales |
| Privacidad | Vertex AI enterprise, PDFs auto-eliminados, GDPR europe-west1 |
| Conexión editorial | Matching con editoriales, perfil verificado, catálogo para profesionales |

## Goals

**Business goal:** Construir la plataforma de referencia para evaluación y descubrimiento de talento literario en español.
**Conversion actions:**
- Escritores: Registro → Subir manuscrito → Obtener informe
- Editoriales: Solicitar acceso → Explorar catálogo → Contactar autores
**Current metrics:** Fase de crecimiento inicial.

## Design Tokens

**Primary color:** #426a65 / #4a7973 (deep teal-green)
**Logo:** "ÅF" (ligature mark)

### WordPress (archivofinal.com)
- Headings: Rufina (serif) — weight 700
- Body: PT Serif (serif) — weight 400
- Text color: #3a3a3a
- Background: #f5f5f5
- Style: Literary, elegant, spacious

### Django App (app.archivofinal.com)
- Headings: Merriweather (serif)
- Body: Inter (sans-serif)
- CSS prefix: .btn-af, .text-af, .bg-af
- Style: Clean, functional, professional
