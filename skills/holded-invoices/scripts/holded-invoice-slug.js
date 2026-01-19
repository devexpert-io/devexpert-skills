#!/usr/bin/env node

function usage() {
  console.error('Usage: holded-invoice-slug "Company Name"');
  process.exit(2);
}

const input = process.argv.slice(2).join(" ").trim();
if (!input) usage();

let s = input.toLowerCase().trim();
s = s
  .replace(/[áàäâ]/g, "a")
  .replace(/[éèëê]/g, "e")
  .replace(/[íìïî]/g, "i")
  .replace(/[óòöô]/g, "o")
  .replace(/[úùüû]/g, "u")
  .replace(/ñ/g, "n");
s = s.replace(/\b(s\.?a\.?|sl|s\.l\.?|srl|ltd|inc|llc|gmbh|bv|oy|ab)\b/g, "");
s = s.replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").replace(/-+/g, "-");
if (!s) s = "empresa";
process.stdout.write(s);
