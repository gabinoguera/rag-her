# Issue 006-02: Extraer design system del legacy → adapters/primary/web/style.css

**Type:** feature
**Status:** open
**Epic:** EPIC-006-frontend-hexagonal

## Description
Extraer los tokens de color, tipografía, utilidades CSS y animaciones del frontend legacy (`rag-estimation-platform`) y crear `adapters/primary/web/style.css` listo para usar en nuestro HTML vanilla con Tailwind CDN.

## Source files (legacy)
- `rag-estimation-platform/config/tailwind.config.js` — tokens de color y borderRadius
- `rag-estimation-platform/app/assets/stylesheets/application.tailwind.css` — variables CSS + utilities

## Tokens a extraer

### Variables CSS (`:root`)
```css
--background: 0 0% 4%;       --foreground: 0 0% 95%;
--card: 0 0% 7%;              --card-foreground: 0 0% 95%;
--primary: 46 78% 59%;        --primary-foreground: 0 0% 4%;
--secondary: 0 0% 12%;        --secondary-foreground: 0 0% 80%;
--muted: 0 0% 10%;            --muted-foreground: 0 0% 55%;
--destructive: 0 62% 50%;     --border: 0 0% 14%;
--input: 0 0% 14%;            --ring: 46 78% 59%;
--radius: 0.625rem;
--surface: 0 0% 9%;           --surface-hover: 0 0% 13%;
--success: 152 60% 42%;       --warning: 38 92% 50%;
--info: 210 80% 56%;
```

### Utilities a portar
- `.glow-sm` / `.glow-md` — box-shadow con color primario
- `.glass` — backdrop-blur + borde semitransparente
- `.animate-fade-in-up` — keyframe entrada suave
- `.stagger-children` — animación en cascada para listas
- Google Fonts: Inter + JetBrains Mono

## Acceptance Criteria
- Existe `adapters/primary/web/style.css` con todos los tokens y utilities
- El fichero es standalone (no depende de Tailwind CLI, funciona con Tailwind CDN play)
- Importa Inter y JetBrains Mono desde Google Fonts
- `.glass`, `.glow-sm`, `.glow-md`, `.animate-fade-in-up`, `.stagger-children` funcionan

## Definition of Done
- [ ] `adapters/primary/web/` directorio creado
- [ ] `adapters/primary/web/style.css` con tokens + utilities
- [ ] Verificado visualmente abriendo un HTML de prueba en el navegador

## Manual Testing Checklist
- Abrir un `test.html` con Tailwind CDN + `<link rel="stylesheet" href="style.css">`
- Aplicar clase `.glass` → debe verse efecto blur
- Aplicar clase `.animate-fade-in-up` → debe animar entrada
- Color `bg-primary` → debe ser el amarillo/chartreuse del legacy

## Notes
Puede ejecutarse en paralelo con `006-01`. La issue `006-03` depende de esta.
Referencia: `rag-estimation-platform/` está en `/Users/simba/Documents/ghen/rag-estimation-platform/`
