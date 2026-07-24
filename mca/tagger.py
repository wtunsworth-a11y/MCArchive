"""Build a self-contained image/map tagging tool.

A single HTML file that lets a person browse every image and map in the archive
and record structured metadata — the event/occasion, people pictured, place,
date and notes. Entries autosave to the browser (localStorage) and can be
exported to JSON/CSV, which is folded back into the searchable index and into
each image's PDF metadata.

Thumbnails are loaded straight from Google Drive by file id, so the file stays
small no matter how many images there are; they render for anyone signed in to
an account that can view the archive.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone


def build_tagger(images: list[dict], folder_name: str = "Document Archive") -> str:
    """``images``: list of dicts with keys id, name, folder, view_url."""
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    payload = [
        {
            "id": im["id"],
            "name": im.get("name", ""),
            "folder": im.get("folder", ""),
            "url": im.get("view_url", ""),
        }
        for im in images
    ]
    return _TEMPLATE.format(
        title=html.escape(folder_name),
        generated=generated,
        total=len(images),
        data_json=json.dumps(payload, ensure_ascii=False),
    )


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Image & Map Tagging</title>
<style>
  :root {{
    --bg:#f6f7f9; --card:#fff; --ink:#1c2330; --muted:#67707f; --line:#e4e7ec;
    --accent:#2c6cf0; --ok:#1f9d55; --okbg:#e7f6ec; --field:#fbfcfe;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg:#0f1420; --card:#171d2b; --ink:#e6e9ef; --muted:#93a0b4; --line:#263041;
      --accent:#5b8dff; --ok:#57c98a; --okbg:#12301f; --field:#0f1522;
    }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font:15px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
         background:var(--bg); color:var(--ink); }}
  header {{ position:sticky; top:0; z-index:5; background:var(--card);
           border-bottom:1px solid var(--line); padding:14px 20px; }}
  h1 {{ margin:0 0 4px; font-size:19px; }}
  .sub {{ color:var(--muted); font-size:13px; }}
  .bar {{ height:8px; background:var(--line); border-radius:6px; margin:10px 0 8px; overflow:hidden; }}
  .bar > i {{ display:block; height:100%; background:var(--ok); width:0; transition:width .2s; }}
  .controls {{ display:flex; gap:10px; flex-wrap:wrap; align-items:center; font-size:13px; }}
  .controls input[type=search] {{ flex:1; min-width:180px; padding:8px 11px; border:1px solid var(--line);
      border-radius:9px; background:var(--bg); color:var(--ink); }}
  button {{ font:inherit; font-size:13px; padding:8px 12px; border:1px solid var(--line);
           background:var(--card); color:var(--ink); border-radius:9px; cursor:pointer; }}
  button.primary {{ background:var(--accent); color:#fff; border-color:transparent; }}
  main {{ max-width:1100px; margin:0 auto; padding:18px 20px 80px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
          padding:14px; margin-bottom:16px; display:grid; grid-template-columns:280px 1fr; gap:16px; }}
  @media (max-width:720px) {{ .card {{ grid-template-columns:1fr; }} }}
  .thumb {{ position:relative; background:var(--bg); border-radius:8px; overflow:hidden;
           min-height:200px; display:flex; align-items:center; justify-content:center; }}
  .thumb img {{ width:100%; height:auto; display:block; }}
  .thumb a.open {{ position:absolute; bottom:6px; right:6px; background:rgba(0,0,0,.6); color:#fff;
                  padding:3px 8px; border-radius:6px; font-size:12px; text-decoration:none; }}
  .fname {{ font-size:12.5px; color:var(--muted); word-break:break-word; margin-bottom:4px; }}
  .folder {{ font-size:11.5px; color:var(--muted); }}
  .done {{ display:none; font-size:11.5px; color:var(--ok); font-weight:600; }}
  .card.tagged {{ border-color:var(--ok); }}
  .card.tagged .done {{ display:inline; }}
  .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
  .grid .full {{ grid-column:1 / -1; }}
  label {{ display:block; font-size:12px; color:var(--muted); margin-bottom:3px; }}
  input[type=text], textarea {{ width:100%; padding:8px 10px; border:1px solid var(--line);
      border-radius:8px; background:var(--field); color:var(--ink); font:inherit; font-size:14px; }}
  textarea {{ resize:vertical; min-height:52px; }}
  .empty {{ text-align:center; color:var(--muted); padding:50px 0; }}
  footer {{ text-align:center; color:var(--muted); font-size:12px; padding:24px; }}
  .saved {{ position:fixed; bottom:16px; left:50%; transform:translateX(-50%);
           background:var(--ok); color:#fff; padding:8px 16px; border-radius:20px; font-size:13px;
           opacity:0; transition:opacity .3s; pointer-events:none; }}
  .saved.show {{ opacity:1; }}
</style>
</head>
<body>
<header>
  <h1>{title} — Image &amp; Map Tagging</h1>
  <div class="sub">Add the event, people and place for each image. Your entries save automatically in this browser.
     When done, click <b>Export</b> and send the file back so it can be merged into the archive.</div>
  <div class="bar"><i id="prog"></i></div>
  <div class="controls">
    <input id="q" type="search" placeholder="Filter by file name or folder…">
    <label style="display:flex;gap:6px;align-items:center;color:var(--muted)">
      <input type="checkbox" id="untagged"> untagged only</label>
    <span id="count" class="sub"></span>
    <span style="flex:1"></span>
    <button id="import">Import…</button>
    <button id="csv">Export CSV</button>
    <button id="export" class="primary">Export JSON</button>
    <input id="file" type="file" accept="application/json" style="display:none">
  </div>
</header>
<main id="list"></main>
<footer>{total} images &middot; tagging sheet generated {generated}. Nothing here is uploaded automatically — export to save your work.</footer>
<div class="saved" id="toast">Saved</div>

<script>
const IMAGES = {data_json};
const KEY = 'mca_tags_v1';
const FIELDS = ['event','people','place','date','notes'];
let store = JSON.parse(localStorage.getItem(KEY) || '{{}}');

const list = document.getElementById('list');
const q = document.getElementById('q');
const untagged = document.getElementById('untagged');
const count = document.getElementById('count');
const prog = document.getElementById('prog');
const toast = document.getElementById('toast');

function esc(s){{ return (s||'').replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c])); }}
function isTagged(id){{ const r=store[id]; return r && FIELDS.some(f=>(r[f]||'').trim()); }}
function thumb(id){{ return 'https://drive.google.com/thumbnail?id='+id+'&sz=w600'; }}

let toastTimer;
function flash(){{ toast.classList.add('show'); clearTimeout(toastTimer);
  toastTimer=setTimeout(()=>toast.classList.remove('show'),900); }}

function save(id, field, val){{
  store[id] = store[id] || {{}};
  store[id][field] = val;
  localStorage.setItem(KEY, JSON.stringify(store));
  const card = document.querySelector('.card[data-id="'+CSS.escape(id)+'"]');
  if(card) card.classList.toggle('tagged', isTagged(id));
  updateProgress(); flash();
}}

function updateProgress(){{
  const done = IMAGES.filter(im=>isTagged(im.id)).length;
  prog.style.width = (IMAGES.length? done/IMAGES.length*100:0)+'%';
  count.textContent = done+' / '+IMAGES.length+' tagged';
}}

function render(){{
  const term = q.value.trim().toLowerCase();
  list.innerHTML='';
  let shown=0;
  IMAGES.forEach(im=>{{
    if(untagged.checked && isTagged(im.id)) return;
    if(term && !(im.name+' '+im.folder).toLowerCase().includes(term)) return;
    shown++;
    const r = store[im.id]||{{}};
    const card=document.createElement('div');
    card.className='card'+(isTagged(im.id)?' tagged':'');
    card.dataset.id=im.id;
    card.innerHTML=`
      <div>
        <div class="thumb">
          <img loading="lazy" src="${{thumb(im.id)}}" alt="${{esc(im.name)}}"
               onerror="this.style.display='none';this.parentNode.insertAdjacentHTML('beforeend','<span class=sub style=padding:20px>Preview needs Drive sign-in</span>')">
          ${{im.url?`<a class="open" href="${{esc(im.url)}}" target="_blank" rel="noopener">Open ↗</a>`:''}}
        </div>
        <div class="fname" title="${{esc(im.name)}}">${{esc(im.name)}} <span class="done">✓ tagged</span></div>
        <div class="folder">📁 ${{esc(im.folder)}}</div>
      </div>
      <div class="grid">
        <div class="full"><label>Event / occasion</label><input type="text" data-f="event" value="${{esc(r.event)}}" placeholder="e.g. Managalas Conservation Area declaration ceremony"></div>
        <div class="full"><label>People (names, comma-separated)</label><input type="text" data-f="people" value="${{esc(r.people)}}" placeholder="e.g. Malchus Kajia, Gunther Joku"></div>
        <div><label>Place</label><input type="text" data-f="place" value="${{esc(r.place)}}" placeholder="e.g. Afore, Oro Province"></div>
        <div><label>Date (approx. ok)</label><input type="text" data-f="date" value="${{esc(r.date)}}" placeholder="e.g. 2017 or Nov 2014"></div>
        <div class="full"><label>Notes / description</label><textarea data-f="notes" placeholder="What is happening, context, source…">${{esc(r.notes)}}</textarea></div>
      </div>`;
    card.querySelectorAll('[data-f]').forEach(el=>{{
      el.addEventListener('change',()=>save(im.id, el.dataset.f, el.value));
    }});
    list.appendChild(card);
  }});
  if(!shown) list.innerHTML='<div class="empty">Nothing matches this filter.</div>';
}}

document.getElementById('export').addEventListener('click',()=>{{
  const rows = IMAGES.map(im=>Object.assign({{id:im.id, name:im.name, folder:im.folder}}, store[im.id]||{{}}));
  download('mca_image_tags.json', JSON.stringify(rows,null,2), 'application/json');
}});
document.getElementById('csv').addEventListener('click',()=>{{
  const head=['id','name','folder',...FIELDS];
  const esc2=v=>'"'+String(v||'').replace(/"/g,'""')+'"';
  const lines=[head.join(',')];
  IMAGES.forEach(im=>{{ const r=store[im.id]||{{}};
    lines.push([im.id,im.name,im.folder,...FIELDS.map(f=>r[f])].map(esc2).join(',')); }});
  download('mca_image_tags.csv', lines.join('\n'), 'text/csv');
}});
document.getElementById('import').addEventListener('click',()=>document.getElementById('file').click());
document.getElementById('file').addEventListener('change',e=>{{
  const f=e.target.files[0]; if(!f) return;
  const rd=new FileReader();
  rd.onload=()=>{{ try{{
      JSON.parse(rd.result).forEach(row=>{{ if(row.id){{ store[row.id]=store[row.id]||{{}};
        FIELDS.forEach(k=>{{ if(row[k]!=null) store[row.id][k]=row[k]; }}); }} }});
      localStorage.setItem(KEY, JSON.stringify(store)); render(); updateProgress();
      alert('Imported. Your previous entries were merged.');
    }}catch(err){{ alert('Could not read that file: '+err); }} }};
  rd.readAsText(f);
}});
function download(name, text, type){{
  const b=new Blob([text],{{type}}); const u=URL.createObjectURL(b);
  const a=document.createElement('a'); a.href=u; a.download=name; a.click(); URL.revokeObjectURL(u);
}}

q.addEventListener('input',render);
untagged.addEventListener('change',render);
render(); updateProgress();
</script>
</body>
</html>
"""
