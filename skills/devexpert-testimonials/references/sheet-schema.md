# Sheet schema (testimonials)

Spreadsheet: configured via `devexpert_testimonials.sheet_id` in `~/.config/skills/config.json`
Tab: configured via `devexpert_testimonials.gid` (optional)

Expected columns:
- Marca temporal -> fecha (dd/mm/yyyy hh:mm:ss)
- Nombre completo -> nombre
- Empresa -> posicion (fallback)
- Puesto en la empresa -> posicion (preferred if present)
- Formacion DevExpert -> titulo del curso
- Testimonio -> texto
- Puntuacion -> rating
- Foto -> Drive URL or local path
- Publicado en web -> marker (any non-empty value)

Notes:
- "Publicado en web": any non-empty value means published.
- The script uses "Puesto en la empresa" if present; otherwise it uses "Empresa".
