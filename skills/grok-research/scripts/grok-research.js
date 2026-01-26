#!/usr/bin/env node

const fs = require("node:fs");
const path = require("node:path");

function die(msg, code = 1) {
  if (msg) console.error(msg);
  process.exit(code);
}

function usage() {
  console.error(
    [
      "Usage:",
      "  grok-research.js --topic \"...\" [--out report.md] [--model <openrouter-model>] [--max-tokens 2200] [--temperature 0.2]",
      "",
      "Env:",
      "  OPENROUTER_API_KEY (required)",
      "  GROK_RESEARCH_MODEL (optional, default: x-ai/grok-4.1-fast:online)",
      "  OPENROUTER_SITE_URL (optional, recommended by OpenRouter)",
      "  OPENROUTER_APP_NAME (optional, recommended by OpenRouter)",
      "",
      "Examples:",
      "  OPENROUTER_API_KEY=... node scripts/grok-research.js --topic \"Qué pasó con …\" --out report.md",
      "  node scripts/grok-research.js --topic \"Rumor X\" --model \"x-ai/grok-4.1-fast:online\"",
    ].join("\n"),
  );
  process.exit(2);
}

function parseArgs(argv) {
  const out = {
    topic: "",
    outPath: "",
    model: "",
    maxTokens: 2200,
    temperature: 0.2,
  };

  const args = argv.slice(2);
  for (let i = 0; i < args.length; i += 1) {
    const a = args[i];
    if (a === "--help" || a === "-h") usage();
    if (a === "--topic") {
      out.topic = String(args[++i] || "").trim();
      continue;
    }
    if (a === "--out") {
      out.outPath = String(args[++i] || "").trim();
      continue;
    }
    if (a === "--model") {
      out.model = String(args[++i] || "").trim();
      continue;
    }
    if (a === "--max-tokens") {
      out.maxTokens = Number(args[++i]);
      continue;
    }
    if (a === "--temperature") {
      out.temperature = Number(args[++i]);
      continue;
    }
    if (!out.topic && !a.startsWith("-")) {
      out.topic = String(a).trim();
      continue;
    }
    die("Unknown arg: " + a, 2);
  }

  if (!out.topic) die("Missing --topic", 2);
  if (!Number.isFinite(out.maxTokens) || out.maxTokens <= 0) die("--max-tokens must be > 0", 2);
  if (!Number.isFinite(out.temperature) || out.temperature < 0 || out.temperature > 2)
    die("--temperature must be between 0 and 2", 2);

  return out;
}

function buildPrompt(topic) {
  const today = new Date().toISOString().slice(0, 10);
  return {
    system: [
      "Eres un analista de investigación. Tu objetivo es investigar temas de actualidad con información reciente y contrastada.",
      "",
      "Instrucciones:",
      "- Prioriza fuentes primarias (comunicados oficiales, documentos, datos) y medios reputados.",
      "- Si hay versiones contradictorias, muestra ambas y explica qué evidencia las respalda.",
      "- Separa claramente hechos vs. interpretación.",
      "- Incluye fechas concretas (YYYY-MM-DD) cuando sea posible.",
      "- Termina con una sección **Fuentes** con una lista de enlaces y, si aplica, enlaces de X.",
      "",
      "Formato de salida (Markdown):",
      "# Informe",
      "## Resumen (5 bullets)",
      "## Qué se sabe (hechos verificados)",
      "## Qué NO se sabe / puntos abiertos",
      "## Línea temporal",
      "## Principales actores",
      "## Claims y verificación (tabla: claim | evidencia | confianza | fuentes)",
      "## Implicaciones / escenarios",
      "## Fuentes (links)",
      "",
      `Fecha de hoy: ${today}`,
    ].join("\n"),
    user: `Tema a investigar: ${topic}`,
  };
}

async function readResponseBody(res) {
  const ct = String(res.headers.get("content-type") || "");
  if (ct.includes("application/json")) {
    try {
      return { kind: "json", value: await res.json() };
    } catch {
      return { kind: "text", value: await res.text() };
    }
  }
  return { kind: "text", value: await res.text() };
}

async function main() {
  const { topic, outPath, model: modelArg, maxTokens, temperature } = parseArgs(process.argv);

  const apiKey = String(process.env.OPENROUTER_API_KEY || "").trim();
  if (!apiKey) die("Missing env var OPENROUTER_API_KEY");

  const model = modelArg || String(process.env.GROK_RESEARCH_MODEL || "").trim() || "x-ai/grok-4.1-fast:online";
  if (!model) die("Missing model (use --model or GROK_RESEARCH_MODEL)");

  if (typeof fetch !== "function") {
    die("This script requires Node.js 18+ (global fetch not available).");
  }

  const { system, user } = buildPrompt(topic);

  const body = {
    model,
    temperature,
    max_tokens: Math.floor(maxTokens),
    messages: [
      { role: "system", content: system },
      { role: "user", content: user },
    ],
  };

  const headers = {
    Authorization: `Bearer ${apiKey}`,
    "Content-Type": "application/json",
  };

  const siteUrl = String(process.env.OPENROUTER_SITE_URL || "").trim();
  const appName = String(process.env.OPENROUTER_APP_NAME || "").trim();
  if (siteUrl) headers["HTTP-Referer"] = siteUrl;
  if (appName) headers["X-Title"] = appName;

  const res = await fetch("https://openrouter.ai/api/v1/chat/completions", {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  const parsed = await readResponseBody(res);
  if (!res.ok) {
    const detail =
      parsed.kind === "json" ? JSON.stringify(parsed.value, null, 2) : String(parsed.value || "").slice(0, 2000);
    die(`OpenRouter error ${res.status} ${res.statusText}\n${detail}`);
  }

  if (parsed.kind !== "json") {
    die("Unexpected non-JSON response from OpenRouter.");
  }

  const text =
    parsed.value &&
    parsed.value.choices &&
    parsed.value.choices[0] &&
    parsed.value.choices[0].message &&
    typeof parsed.value.choices[0].message.content === "string"
      ? parsed.value.choices[0].message.content
      : "";

  if (!text) {
    die("OpenRouter response missing choices[0].message.content");
  }

  if (outPath) {
    const abs = path.resolve(outPath);
    fs.mkdirSync(path.dirname(abs), { recursive: true });
    fs.writeFileSync(abs, text, "utf8");
    process.stdout.write(abs + "\n");
    return;
  }

  process.stdout.write(text);
}

main().catch((err) => {
  die(err && err.stack ? err.stack : String(err));
});

