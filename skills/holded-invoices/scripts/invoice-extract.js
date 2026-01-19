#!/usr/bin/env node

const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

function die(msg) {
  console.error(msg);
  process.exit(1);
}

function usage() {
  console.error("Usage: invoice-extract.js --pdf /path/to/invoice.pdf");
  process.exit(2);
}

function slugifyVendor(name) {
  let s = String(name || "").trim().toLowerCase();
  s = s
    .replace(/[áàäâ]/g, "a")
    .replace(/[éèëê]/g, "e")
    .replace(/[íìïî]/g, "i")
    .replace(/[óòöô]/g, "o")
    .replace(/[úùüû]/g, "u")
    .replace(/ñ/g, "n");
  s = s.replace(/\b(s\.?a\.?|sl|s\.l\.?|srl|ltd|inc|llc|gmbh|bv|oy|ab)\b/g, "");
  s = s.replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").replace(/-+/g, "-");
  if (!s) return "empresa";
  return s;
}

function extractText(pdfPath) {
  const out = spawnSync("pdftotext", [pdfPath, "-"], { encoding: "utf8" });
  if (out.status !== 0) {
    die(out.stderr || "pdftotext failed");
  }
  return String(out.stdout || "");
}

function findDate(text) {
  const candidates = [];

  // YYYY-MM-DD or YYYY/MM/DD
  for (const m of text.matchAll(/\b(20\d{2})[-\/](0?[1-9]|1[0-2])[-\/](0?[1-9]|[12]\d|3[01])\b/g)) {
    candidates.push({ year: m[1], month: m[2] });
  }

  // DD/MM/YYYY or DD-MM-YYYY
  for (const m of text.matchAll(/\b(0?[1-9]|[12]\d|3[01])[-\/](0?[1-9]|1[0-2])[-\/](20\d{2})\b/g)) {
    candidates.push({ year: m[3], month: m[2] });
  }

  if (candidates.length === 0) return null;

  // Prefer first reasonable candidate.
  const c = candidates[0];
  const year = String(c.year);
  const month = String(c.month).padStart(2, "0");
  return { year, month };
}

function findVendor(text) {
  const rawLines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)
    .slice(0, 80);

  const stop = new Set([
    "factura",
    "invoice",
    "receipt",
    "bill",
    "sold to",
    "invoice summary",
    "billing overview",
    "overview",
    "total",
    "subtotal",
    "iva",
    "vat",
    "impuestos",
    "fecha",
    "date",
  ]);

  function normalizeCandidate(line) {
    const firstChunk = line.split("•")[0].split("|")[0].trim();
    return firstChunk.replace(/[#*·]/g, "").trim();
  }

  function score(line) {
    const lc = line.toLowerCase();
    let s = 0;
    if (/\b(gmbh|limited|ltd\.?|inc\.?|llc|s\.?l\.?u\.?|s\.?l\.?|s\.a\.?|bv)\b/i.test(line)) s += 3;
    if (/\b(online|technologies|systems|software|services)\b/i.test(line)) s += 1;
    if (line.length >= 4 && line.length <= 50) s += 1;
    return s;
  }

  const candidates = [];
  for (const line of rawLines) {
    const cleaned = normalizeCandidate(line);
    if (cleaned.length < 3) continue;
    const lc = cleaned.toLowerCase();
    if (stop.has(lc)) continue;
    if (/^page\s+\d+\s+of\s+\d+$/i.test(cleaned)) continue;
    if (/^\d+$/.test(cleaned)) continue;
    if (/(www\.|https?:\/\/|@)/i.test(cleaned)) continue;
    if (/\b(cif|nif|vat|tax)\b/i.test(cleaned)) continue;
    if (/\b(factura|invoice|recibo|receipt)\b/i.test(cleaned)) continue;
    if (!/[a-záéíóúñ]/i.test(cleaned)) continue;

    candidates.push({ value: cleaned, score: score(cleaned) });
  }

  if (candidates.length === 0) return "";
  candidates.sort((a, b) => b.score - a.score);
  return candidates[0].value;
}

const args = process.argv.slice(2);
const pdfIdx = args.indexOf("--pdf");
if (pdfIdx === -1) usage();
const pdfPath = args[pdfIdx + 1];
if (!pdfPath) usage();

const resolved = path.resolve(pdfPath);
if (!fs.existsSync(resolved)) {
  die("PDF not found: " + resolved);
}

const text = extractText(resolved);
const vendor = findVendor(text);
const date = findDate(text);

const vendorSlug = slugifyVendor(vendor || path.basename(resolved, path.extname(resolved)));

const out = {
  vendor,
  vendorSlug,
  year: date ? date.year : "",
  month: date ? date.month : "",
};

process.stdout.write(JSON.stringify(out));
