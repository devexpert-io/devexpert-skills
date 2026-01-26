# OpenRouter API notes (para `grok-research`)

## Endpoint

- `POST https://openrouter.ai/api/v1/chat/completions`

## Auth

- Header: `Authorization: Bearer $OPENROUTER_API_KEY`

Headers recomendados por OpenRouter (opcionales pero útiles):
- `HTTP-Referer: $OPENROUTER_SITE_URL`
- `X-Title: $OPENROUTER_APP_NAME`

## Request (shape)

Campos comunes usados por `scripts/grok-research.js`:
- `model` (string): modelo en OpenRouter (ej: `x-ai/grok-4.1-fast:online`)
- `messages`: array `{role, content}`
- `max_tokens` (number)
- `temperature` (number)

## Respuesta

- `choices[0].message.content` contiene el Markdown del informe.

## Troubleshooting rápido

- 401/403: API key incorrecta o sin permisos.
- 404/400: `model` inválido → usa `--model ...` o `GROK_RESEARCH_MODEL`.
- Contenido “viejo”: usa variante “online” si el modelo la ofrece (p.ej. sufijo `:online` en algunos modelos).
