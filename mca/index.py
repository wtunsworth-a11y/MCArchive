"""Build a single self-contained, searchable HTML index of the archive.

The output is one ``index.html`` file with all document metadata and OCR text
embedded as JSON and a small client-side search UI — no server, no external
assets — so it works whether opened locally or from Google Drive.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone


def _size(n: int) -> str:
    step = 0
    f = float(n)
    while f >= 1024 and step < 3:
        f /= 1024
        step += 1
    unit = ("B", "KB", "MB", "GB")[step]
    return f"{f:.0f} {unit}" if step == 0 else f"{f:.1f} {unit}"


def build_index(docs: list[dict], folder_name: str = "Document Archive") -> str:
    """Return the full HTML for the searchable index."""
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total = len(docs)
    dup_docs = sum(1 for d in docs if d.get("duplicate_group"))
    dup_groups = len({d["duplicate_group"] for d in docs if d.get("duplicate_group")})
    title_flagged = sum(1 for d in docs if d.get("title_flag"))
    total_pages = sum(d.get("pages", 0) for d in docs)

    # Embed a trimmed record (cap OCR text so the file stays manageable).
    payload = []
    for d in docs:
        payload.append({
            "id": d["id"],
            "title": d.get("title") or d.get("source_name", ""),
            "source_name": d.get("source_name", ""),
            "folder": d.get("rel_folder", ""),
            "type": d.get("file_type", ""),
            "action": d.get("action", ""),
            "keywords": d.get("keywords", []),
            "dates": d.get("dates", []),
            "pages": d.get("pages", 0),
            "size": _size(d.get("size_bytes", 0)),
            "snippet": d.get("snippet", ""),
            "text": (d.get("text", "") or "")[:20000],
            "url": d.get("url", ""),
            "dup_group": d.get("duplicate_group"),
            "dup_kind": d.get("duplicate_kind", ""),
            "dup_matches": d.get("duplicate_matches", []),
            "rotated": d.get("rotated", False),
            "title_flag": d.get("title_flag", ""),
            "title_reason": d.get("title_reason", ""),
            "title_suggested": d.get("title_suggested", ""),
        })

    data_json = json.dumps(payload, ensure_ascii=False)
    title_esc = html.escape(folder_name)

    return _TEMPLATE.format(
        title=title_esc,
        generated=generated,
        total=total,
        total_pages=total_pages,
        dup_docs=dup_docs,
        dup_groups=dup_groups,
        title_flagged=title_flagged,
        data_json=data_json,
    )


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Searchable Index</title>
<style>
  :root {{
    --bg:#f6f7f9; --card:#fff; --ink:#1c2330; --muted:#67707f;
    --line:#e4e7ec; --accent:#2c6cf0; --chip:#eef2fb; --chip-ink:#2c4a8f;
    --warn-bg:#fff4e5; --warn-ink:#8a5300; --warn-line:#f5d9a8;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg:#0f1420; --card:#171d2b; --ink:#e6e9ef; --muted:#93a0b4;
      --line:#26304180; --accent:#5b8dff; --chip:#1d2740; --chip-ink:#a9c2ff;
      --warn-bg:#332711; --warn-ink:#f0c674; --warn-line:#5a4718;
    }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font:15px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
         background:var(--bg); color:var(--ink); }}
  header {{ position:sticky; top:0; z-index:5; background:var(--card);
           border-bottom:1px solid var(--line); padding:16px 20px; }}
  h1 {{ margin:0 0 10px; font-size:20px; }}
  .stats {{ color:var(--muted); font-size:13px; margin-bottom:12px; }}
  .stats b {{ color:var(--ink); }}
  #q {{ width:100%; padding:11px 14px; font-size:15px; border:1px solid var(--line);
       border-radius:10px; background:var(--bg); color:var(--ink); }}
  #q:focus {{ outline:2px solid var(--accent); border-color:transparent; }}
  .toolbar {{ display:flex; gap:14px; align-items:center; margin-top:10px; font-size:13px;
             color:var(--muted); flex-wrap:wrap; }}
  .toolbar label {{ display:flex; gap:6px; align-items:center; cursor:pointer; }}
  main {{ max-width:1000px; margin:0 auto; padding:18px 20px 60px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
          padding:16px 18px; margin-bottom:14px; }}
  .card h2 {{ margin:0 0 6px; font-size:16px; }}
  .card h2 a {{ color:var(--accent); text-decoration:none; }}
  .card h2 a:hover {{ text-decoration:underline; }}
  .meta {{ font-size:12px; color:var(--muted); margin-bottom:8px; }}
  .meta span {{ margin-right:12px; }}
  .snippet {{ font-size:13.5px; color:var(--ink); opacity:.85; margin:8px 0; }}
  .chips {{ display:flex; flex-wrap:wrap; gap:6px; }}
  .chip {{ background:var(--chip); color:var(--chip-ink); border-radius:20px;
          padding:2px 10px; font-size:12px; }}
  .chip.k {{ cursor:pointer; }}
  .dup {{ display:block; background:var(--warn-bg); color:var(--warn-ink);
         border:1px solid var(--warn-line); border-radius:6px; padding:2px 8px;
         font-size:11.5px; font-weight:600; margin-bottom:6px; }}
  .dup.title {{ background:var(--chip); color:var(--chip-ink); border-color:transparent; font-weight:500; }}
  .dup.title b {{ font-weight:700; }}
  mark {{ background:#ffe58a; color:#3a2d00; padding:0 1px; border-radius:2px; }}
  .empty {{ text-align:center; color:var(--muted); padding:50px 0; }}
  footer {{ text-align:center; color:var(--muted); font-size:12px; padding:24px; }}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <div class="stats">
    <b>{total}</b> documents &middot; <b>{total_pages}</b> pages &middot;
    <b>{dup_docs}</b> possible duplicates in <b>{dup_groups}</b> group(s) &middot;
    <b>{title_flagged}</b> titles to review &middot;
    indexed {generated}
  </div>
  <input id="q" type="search" placeholder="Search titles, keywords and full text…" autofocus>
  <div class="toolbar">
    <label><input type="checkbox" id="dupOnly"> possible duplicates only</label>
    <label><input type="checkbox" id="titleOnly"> titles to review only</label>
    <span id="count"></span>
  </div>
</header>
<main id="results"></main>
<footer>Generated by the MCA Document Archive pipeline. Duplicates are flagged for review — nothing was deleted.</footer>

<script>
const DOCS = {data_json};
const results = document.getElementById('results');
const q = document.getElementById('q');
const dupOnly = document.getElementById('dupOnly');
const titleOnly = document.getElementById('titleOnly');
const count = document.getElementById('count');

function esc(s){{ return (s||'').replace(/[&<>"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c])); }}
function highlight(text, terms){{
  let out = esc(text);
  terms.forEach(t => {{
    if(!t) return;
    const re = new RegExp('('+t.replace(/[.*+?^{{}}()|[\]\\]/g,'\\$&')+')','ig');
    out = out.replace(re, '<mark>$1</mark>');
  }});
  return out;
}}
function matchContext(doc, terms){{
  const t = doc.text.toLowerCase();
  for(const term of terms){{
    const i = t.indexOf(term.toLowerCase());
    if(i >= 0){{
      const start = Math.max(0, i-80);
      return (start>0?'…':'') + doc.text.slice(start, i+term.length+120) + '…';
    }}
  }}
  return doc.snippet;
}}

function render(){{
  const raw = q.value.trim().toLowerCase();
  const terms = raw ? raw.split(/\s+/) : [];
  let shown = 0;
  results.innerHTML = '';
  DOCS.forEach(doc => {{
    if(dupOnly.checked && !doc.dup_group) return;
    if(titleOnly.checked && !doc.title_flag) return;
    const hay = (doc.title+' '+doc.source_name+' '+doc.folder+' '+doc.keywords.join(' ')+' '+doc.text).toLowerCase();
    if(terms.length && !terms.every(t => hay.includes(t))) return;
    shown++;
    const context = terms.length ? matchContext(doc, terms) : doc.snippet;
    const dupBadge = doc.dup_group
      ? `<div class="dup">⚠ Possible ${{doc.dup_kind}} duplicate (group ${{doc.dup_group}}) — matches: ${{esc(doc.dup_matches.join(', '))}}</div>` : '';
    const titleBadge = doc.title_flag
      ? `<div class="dup title">✎ Title to review — ${{esc(doc.title_reason)}}${{doc.title_suggested?`. Suggested: <b>${{esc(doc.title_suggested)}}</b>`:''}}</div>` : '';
    const link = doc.url
      ? `<a href="${{esc(doc.url)}}" target="_blank" rel="noopener">${{highlight(doc.title, terms)}}</a>`
      : highlight(doc.title, terms);
    const chips = doc.keywords.map(k =>
      `<span class="chip k" data-k="${{esc(k)}}">${{highlight(k, terms)}}</span>`).join('');
    const dates = doc.dates.length ? `<span>📅 ${{esc(doc.dates.join(', '))}}</span>` : '';
    const typeBadge = doc.type ? `<span class="chip" style="text-transform:uppercase">${{esc(doc.type)}}</span>` : '';
    const catalogued = doc.action === 'catalogued'
      ? '<span title="listed only; not converted">🗂 catalogued</span>' : '';
    const folder = doc.folder ? `<span title="folder">📁 ${{esc(doc.folder)}}</span>` : '';
    const pages = doc.pages ? `<span>📄 ${{doc.pages}} pp</span>` : '';
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `
      ${{dupBadge}}${{titleBadge}}
      <h2>${{link}}</h2>
      <div class="meta">${{pages}}<span>${{esc(doc.size)}}</span>
        <span title="original file">${{esc(doc.source_name)}}</span>${{folder}}${{dates}}
        ${{doc.rotated?'<span>↻ rotation corrected</span>':''}}${{catalogued}}</div>
      <div class="snippet">${{highlight(context, terms)}}</div>
      <div class="chips">${{typeBadge}}${{chips}}</div>`;
    results.appendChild(card);
  }});
  count.textContent = shown + ' / ' + DOCS.length + ' shown';
  if(shown === 0) results.innerHTML = '<div class="empty">No documents match your search.</div>';
}}

results.addEventListener('click', e => {{
  const chip = e.target.closest('.chip.k');
  if(chip){{ q.value = chip.dataset.k; render(); window.scrollTo({{top:0,behavior:'smooth'}}); }}
}});
q.addEventListener('input', render);
dupOnly.addEventListener('change', render);
titleOnly.addEventListener('change', render);
render();
</script>
</body>
</html>
"""
