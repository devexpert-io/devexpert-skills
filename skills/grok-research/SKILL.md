---
name: grok-research
description: "Investiga temas de actualidad con Grok 4.1 vía OpenRouter y genera un informe en Markdown con línea temporal, claims verificables y fuentes (web/X). Úsala cuando necesites research rápido y contrastado (noticias, rumores, cambios de producto/política, contexto competitivo)."
---

# Grok research (OpenRouter + Grok 4.1)

Esta skill automatiza un “deep dive” sobre un tema reciente usando Grok 4.1 a través de OpenRouter, devolviendo un informe en Markdown con fuentes.

## Quick start

1) Exporta la API key en entorno:

```bash
export OPENROUTER_API_KEY="..."
```

2) Ejecuta el script:

```bash
node skills/grok-research/scripts/grok-research.js --topic "Qué está pasando con …" --out report.md
```

Por defecto intenta usar `x-ai/grok-4.1-fast:online`. Si tu cuenta/modelo usa otro nombre, pasa `--model` o define `GROK_RESEARCH_MODEL`.

## Variables de entorno

- `OPENROUTER_API_KEY` (requerida)
- `GROK_RESEARCH_MODEL` (opcional) (default: `x-ai/grok-4.1-fast:online`)
- `OPENROUTER_SITE_URL` (opcional) (header recomendado por OpenRouter)
- `OPENROUTER_APP_NAME` (opcional) (header recomendado por OpenRouter)

## Flags útiles (script)

- `--topic "..."`: tema a investigar (o primer argumento posicional)
- `--out report.md`: guarda el informe y escribe la ruta resultante por stdout
- `--model <id>`: fuerza el modelo de OpenRouter
- `--max-tokens 2200`, `--temperature 0.2`: control de longitud/estilo

## Workflow recomendado (agente)

1) Clarifica el objetivo: “¿quieres un resumen ejecutivo o un informe para tomar decisiones?”
2) Pide constraints: país/idioma, horizonte temporal (últimas 24/72h), y si hay afirmaciones concretas a verificar.
3) Ejecuta `scripts/grok-research.js` y revisa el bloque **Claims y verificación**:
   - Si faltan fuentes, re-lanza con un `--max-tokens` mayor o ajusta el topic para ser más específico.
4) Si el tema es sensible/controvertido, pide al modelo que liste hipótesis alternativas y qué evidencia faltaría para confirmarlas.

## Recursos

- Script principal: `scripts/grok-research.js`
- Notas API: `references/api_reference.md`
