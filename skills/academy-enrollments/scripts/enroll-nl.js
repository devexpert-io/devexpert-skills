#!/usr/bin/env node

const { spawnSync } = require("node:child_process");
const path = require("node:path");

function usage() {
  console.error("Usage:");
  console.error(
    '  enroll-nl "Enroll Ana Pérez (ana@acme.com) in AI Expert precio 997"'
  );
  console.error("");
  console.error("Accepted patterns (best effort):");
  console.error("- Must include an email");
  console.error("- Must include a course name after 'en'");
  console.error("- Name can be before the email, optionally in parentheses");
  process.exit(2);
}

const input = process.argv.slice(2).join(" ").trim();
if (!input) usage();

const emailMatch = input.match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i);
if (!emailMatch) {
  console.error("Could not find an email in: " + input);
  process.exit(2);
}
const email = emailMatch[0];

const precioMatch = input.match(/(?:precio|€)\s*([0-9]{2,6})/i);
const precio = precioMatch ? precioMatch[1] : "";

let formacion = "";
{
  const m = input.match(/\ben\s+([^()]+?)(?:\s+(?:precio|€)\b|$)/i);
  if (m) formacion = m[1].trim();
  formacion = formacion.replace(/[.。,;]+\s*$/, "");
}
if (!formacion) {
  console.error("Could not find course name after 'en' in: " + input);
  process.exit(2);
}

let fullName = "";
{
  const pre = input.slice(0, emailMatch.index).trim();
  const m = pre.match(/\b(?:a|al|para)\s+(.+)$/i);
  fullName = (m ? m[1] : pre).trim();
  fullName = fullName.replace(/[([].*$/, "").trim();
  fullName = fullName.replace(/[:,\-]+\s*$/, "").trim();
}

const nameParts = fullName.split(/\s+/).filter(Boolean);
if (nameParts.length < 2) {
  console.error(
    "Could not confidently parse full name (need nombre + apellidos). Parsed: '" +
      fullName +
      "'"
  );
  console.error(
    "Tip: use: 'Da de alta a Nombre Apellidos (email@dom.com) en AI Expert'"
  );
  process.exit(2);
}
const nombre = nameParts[0];
const apellidos = nameParts.slice(1).join(" ");

const script = path.resolve(__dirname, "enroll-grant-access.sh");
const args = [
  script,
  "--email",
  email,
  "--nombre",
  nombre,
  "--apellidos",
  apellidos,
  "--formacion",
  formacion,
];
if (precio) {
  args.push("--precio", precio);
}

const res = spawnSync(args[0], args.slice(1), { stdio: "inherit" });
process.exit(res.status ?? 1);
