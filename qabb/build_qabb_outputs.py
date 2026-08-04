#!/usr/bin/env python3
"""Assemble the QABB deliverables from the on-disk working data:

  qabb/QABB_document_index.html   full-text searchable index (links -> shared dest files)
  qabb/QABB_image_tagging.html    image tagging tool (prefilled tags + clarity flag)
  qabb/QABB_duplicate_report.csv  near-duplicate groups (Jaccard >= 0.80 5-gram shingles)
  qabb/QABB_long_filename_rename_sheet.csv  suggested shorter names for long/awkward files

Inputs (all under WORK):
  docs_manifest.json          [{drive_id,title,folder,mime,size,url}, ...]
  text/<drive_id>.txt         extracted full text per doc (may be empty for scanned)
  pdf_copies.csv              src_id,title,folder,new_id,new_url   (dest copies of PDFs)
  image_copies.csv            filing_name,original_name,folder,old_id,new_id,new_url
Optional:
  office_pdfs.csv             src_id,title,folder,new_id,new_url   (converted Office->PDF dest copies)
"""
from __future__ import annotations
import csv, json, os, re, sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
from mca.text import extract_keywords, extract_dates, snippet, ocr_quality  # noqa
from mca.dedup import find_duplicates, DupDoc  # noqa
from mca.index import build_index  # noqa

WORK = sys.argv[1] if len(sys.argv) > 1 else \
    "/tmp/claude-0/-home-user-MCArchive/86d1fa9a-da03-5bca-b28a-0db92371dcef/scratchpad/qabb_work"
NAME = "QABB Archive"


def load_csv(path):
    return list(csv.DictReader(open(path))) if os.path.exists(path) else []


def fix_letterspacing(t: str) -> str:
    """Some PDFs extract as 'C o ns e rvatio n'. If a line is mostly 1-2 char
    tokens, rejoin runs of single chars into words. Conservative: only acts on
    lines where >55% of tokens are length<=2."""
    out = []
    for line in t.splitlines():
        toks = line.split()
        if len(toks) >= 8:
            short = sum(1 for w in toks if len(w) <= 2)
            if short / len(toks) > 0.55:
                # join single-letter runs; keep 2+ char tokens as boundaries
                rebuilt, buf = [], []
                for w in toks:
                    if len(w) == 1:
                        buf.append(w)
                    else:
                        if buf:
                            rebuilt.append("".join(buf)); buf = []
                        rebuilt.append(w)
                if buf:
                    rebuilt.append("".join(buf))
                line = " ".join(rebuilt)
        out.append(line)
    return "\n".join(out)


def main():
    manifest = json.load(open(f"{WORK}/docs_manifest.json"))
    pdf_copies = {r["src_id"]: r for r in load_csv(f"{WORK}/pdf_copies.csv")}
    office_pdfs = {r["src_id"]: r for r in load_csv(f"{WORK}/office_pdfs.csv")}
    img_rows = load_csv(f"{WORK}/image_copies.csv")

    docs = []
    for m in manifest:
        did = m["drive_id"]
        tpath = f"{WORK}/text/{did}.txt"
        text = ""
        if os.path.exists(tpath):
            text = open(tpath, encoding="utf-8", errors="ignore").read()
            if text:
                text = fix_letterspacing(text)
        # destination url: prefer converted Office PDF, then copied PDF, then source
        dest = office_pdfs.get(did) or pdf_copies.get(did)
        url = dest["new_url"] if dest else m["url"]
        source_name = m["title"]
        # title: use filename stem cleaned; avoid ALL-CAPS logo lines
        title = re.sub(r"\.[A-Za-z0-9]+$", "", source_name)
        kws = extract_keywords(text, 12) if text else []
        docs.append({
            "id": did,
            "title": title,
            "source_name": source_name,
            "rel_folder": m["folder"],
            "file_type": (m["mime"].split("/")[-1].split(".")[-1] or "pdf")[:5],
            "action": "processed",
            "keywords": kws,
            "dates": extract_dates(text) if text else [],
            "pages": 0,
            "size_bytes": int(m["size"]),
            "snippet": snippet(text) if text else "(no extractable text — scanned; OCR pending)",
            "text": text[:20000],
            "url": url,
            "_ocrq": ocr_quality(text) if text else 0.0,
            "_chars": len(text),
        })

    # ---- de-duplication ----
    # Two signals, because the biggest duplicates are scanned volumes with NO
    # extractable text (Jaccard can't see them): (a) same filename => same
    # document; (b) text Jaccard >= 0.65 of 5-gram shingles.
    from collections import defaultdict
    from mca.dedup import _shingles, _tokens, _jaccard
    for d in docs:
        d["duplicate_group"] = None
        d["duplicate_kind"] = ""
        d["duplicate_matches"] = []
        d["dup_removed"] = False        # excluded from the archive as a redundant copy
        d["dup_keep_note"] = ""

    groups = {}   # gid -> list[doc]
    gid = 0
    used = set()

    # (a) same-name groups -> genuine duplicates; keep the most-text copy
    byname = defaultdict(list)
    for d in docs:
        byname[d["source_name"].lower()].append(d)
    for name, members in byname.items():
        if len(members) < 2:
            continue
        gid += 1
        keep = max(members, key=lambda x: (x["_chars"], -x["size_bytes"]))
        for d in members:
            d["duplicate_group"] = gid
            d["duplicate_kind"] = "same-name"
            d["duplicate_matches"] = [m["source_name"] for m in members if m is not d]
            used.add(d["id"])
            if d is not keep:
                d["dup_removed"] = True
                d["dup_keep_note"] = f"redundant copy of «{keep['source_name']}» kept in {keep['rel_folder']}"
            else:
                d["dup_keep_note"] = "kept (best text copy)"
        groups[gid] = members

    # (b) text-similar pairs >= 0.65 among not-yet-grouped -> RELATED (keep both)
    sh = {d["id"]: _shingles(_tokens(d["text"])) for d in docs}
    pairs = []
    for i in range(len(docs)):
        a = docs[i]
        if not sh[a["id"]]:
            continue
        for j in range(i + 1, len(docs)):
            b = docs[j]
            if not sh[b["id"]]:
                continue
            s = _jaccard(sh[a["id"]], sh[b["id"]])
            if s >= 0.65:
                pairs.append((s, a, b))
    for s, a, b in sorted(pairs, reverse=True):
        if a["id"] in used and b["id"] in used and a["duplicate_group"] == b["duplicate_group"] and a["duplicate_group"]:
            continue
        gid += 1
        for d in (a, b):
            d.setdefault("_relgroups", []).append(gid)
            if not d["duplicate_group"]:
                d["duplicate_group"] = gid
            d["duplicate_kind"] = f"related~{s:.2f}"
            used.add(d["id"])
        a["duplicate_matches"] = sorted(set(a["duplicate_matches"]) | {b["source_name"]})
        b["duplicate_matches"] = sorted(set(b["duplicate_matches"]) | {a["source_name"]})
        groups[gid] = [a, b]

    # ---- duplicate report CSV (all groups) ----
    with open(f"{HERE}/QABB_duplicate_report.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["group", "kind", "decision", "folder", "source_name",
                    "size_bytes", "chars", "drive_url", "matches"])
        for g in sorted(groups):
            for d in sorted(groups[g], key=lambda x: -x["size_bytes"]):
                decision = ("REMOVE (redundant)" if d["dup_removed"]
                            else "keep" if d["duplicate_kind"] == "same-name"
                            else "keep (related)")
                w.writerow([g, d["duplicate_kind"], decision, d["rel_folder"], d["source_name"],
                            d["size_bytes"], d["_chars"], d["url"], "; ".join(d["duplicate_matches"])])

    # ---- explicit "delete these redundant destination copies" sheet ----
    with open(f"{HERE}/QABB_duplicates_to_delete.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["source_name", "folder", "size_bytes", "reason", "destination_copy_url_to_delete"])
        for d in docs:
            if d["dup_removed"]:
                w.writerow([d["source_name"], d["rel_folder"], d["size_bytes"],
                            d["dup_keep_note"], d["url"]])

    # ---- long / awkward filename rename sheet ----
    def awkward(name):
        stem = re.sub(r"\.[A-Za-z0-9]+$", "", name)
        reasons = []
        if len(name) > 90:
            reasons.append("long(>90)")
        if "~" in stem or re.search(r"~\d", stem):
            reasons.append("dos-truncated")
        if re.search(r"\s{2,}", name) or name != name.strip():
            reasons.append("whitespace")
        if re.search(r"\(\d+\)", name):
            reasons.append("copy-suffix")
        return reasons

    with open(f"{HERE}/QABB_long_filename_rename_sheet.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["folder", "current_name", "issues", "char_len", "suggested_name", "drive_url"])
        for d in sorted(docs, key=lambda x: x["rel_folder"]):
            issues = awkward(d["source_name"])
            if not issues:
                continue
            stem = re.sub(r"\.[A-Za-z0-9]+$", "", d["source_name"])
            ext = d["source_name"][len(stem):]
            suggested = re.sub(r"\s+", " ", stem).strip()
            suggested = re.sub(r"\s*\(\d+\)", "", suggested)[:86] + ext
            w.writerow([d["rel_folder"], d["source_name"], ";".join(issues),
                        len(d["source_name"]), suggested, d["url"]])

    # ---- searchable index ----
    # flag low/no-text docs in the index via title_flag mechanism (reused UI slot)
    for d in docs:
        if d["_chars"] < 40:
            d["title_flag"] = "scanned"
            d["title_reason"] = "no extractable text yet — scanned volume; OCR pending"
            d["title_suggested"] = ""
        elif d["_ocrq"] and d["_ocrq"] < 0.6:
            d["title_flag"] = "lowocr"
            d["title_reason"] = f"low text-quality score ({d['_ocrq']}) — may need re-OCR"
            d["title_suggested"] = ""
    # exclude redundant duplicate copies from the searchable archive
    docs_index = [d for d in docs if not d["dup_removed"]]
    html = build_index(docs_index, folder_name=NAME)
    open(f"{HERE}/QABB_document_index.html", "w", encoding="utf-8").write(html)

    # ---- image tagging tool (with clarity flag + folder prefill) ----
    images = [{
        "id": r.get("new_id") or r.get("old_id"),
        "name": r["filing_name"],
        "original": r["original_name"],
        "folder": r["folder"],
        "url": r.get("new_url", ""),
    } for r in img_rows if (r.get("new_id") or r.get("old_id"))]
    open(f"{HERE}/QABB_image_tagging.html", "w", encoding="utf-8").write(build_tagger(images))

    # ---- console summary ----
    scanned = sum(1 for d in docs if d["_chars"] < 40)
    lowocr = sum(1 for d in docs if 40 <= d["_chars"] and d["_ocrq"] and d["_ocrq"] < 0.6)
    print(f"docs indexed: {len(docs)}  | with text: {sum(1 for d in docs if d['_chars']>=40)}"
          f"  | scanned/no-text: {scanned}  | low-ocr: {lowocr}")
    print(f"duplicate groups: {len(groups)}  ({sum(len(v) for v in groups.values())} docs)")
    print(f"images in tagging tool: {len(images)}")
    print("Wrote: QABB_document_index.html, QABB_image_tagging.html, "
          "QABB_duplicate_report.csv, QABB_long_filename_rename_sheet.csv")


IMG_TEMPLATE = None  # set below


def build_tagger(images):
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    # folder-based prefill hints
    def prefill(im):
        f = im["folder"].lower(); n = im["original"].lower()
        place = "Oro Province, PNG"
        event = ""
        if "ornale" in f or "ornale" in n or "b_f" in n or "b_m" in n:
            event = "Ornithoptera alexandrae (Queen Alexandra's Birdwing) specimen"
        elif "parari" in f or "par_flower" in n or "aristolochia" in n:
            event = "Pararistolochia (host vine)"
        elif "general" in f:
            event = "QABB fieldwork / general"
        return {"event": event, "place": place}
    payload = [{
        "id": im["id"], "name": im["name"], "original": im["original"],
        "folder": im["folder"], "url": im["url"], **prefill(im),
    } for im in images]
    return _TAGGER.replace("__DATA__", json.dumps(payload, ensure_ascii=False)) \
                  .replace("__TOTAL__", str(len(images))) \
                  .replace("__GEN__", generated)


_TAGGER = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QABB — Image &amp; Map Tagging</title>
<style>
 :root{--bg:#f6f7f9;--card:#fff;--ink:#1c2330;--muted:#67707f;--line:#e4e7ec;--accent:#2c6cf0;--ok:#1f9d55;--field:#fbfcfe;--soft:#8a5300;--blur:#b42318;}
 @media(prefers-color-scheme:dark){:root{--bg:#0f1420;--card:#171d2b;--ink:#e6e9ef;--muted:#93a0b4;--line:#263041;--accent:#5b8dff;--ok:#57c98a;--field:#0f1522;--soft:#f0c674;--blur:#ff9a8a;}}
 *{box-sizing:border-box}body{margin:0;font:15px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;background:var(--bg);color:var(--ink)}
 header{position:sticky;top:0;z-index:5;background:var(--card);border-bottom:1px solid var(--line);padding:14px 20px}
 h1{margin:0 0 4px;font-size:19px}.sub{color:var(--muted);font-size:13px}
 .bar{height:8px;background:var(--line);border-radius:6px;margin:10px 0 8px;overflow:hidden}.bar>i{display:block;height:100%;background:var(--ok);width:0;transition:width .2s}
 .controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;font-size:13px}
 .controls input[type=search]{flex:1;min-width:180px;padding:8px 11px;border:1px solid var(--line);border-radius:9px;background:var(--bg);color:var(--ink)}
 button{font:inherit;font-size:13px;padding:8px 12px;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:9px;cursor:pointer}
 button.primary{background:var(--accent);color:#fff;border-color:transparent}
 main{max-width:1100px;margin:0 auto;padding:18px 20px 80px}
 .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin-bottom:16px;display:grid;grid-template-columns:280px 1fr;gap:16px}
 @media(max-width:720px){.card{grid-template-columns:1fr}}
 .thumb{position:relative;background:var(--bg);border-radius:8px;overflow:hidden;min-height:200px;display:flex;align-items:center;justify-content:center}
 .thumb img{width:100%;height:auto;display:block}
 .thumb a.open{position:absolute;bottom:6px;right:6px;background:rgba(0,0,0,.6);color:#fff;padding:3px 8px;border-radius:6px;font-size:12px;text-decoration:none}
 .fname{font-size:12.5px;color:var(--muted);word-break:break-word;margin-bottom:4px}.folder{font-size:11.5px;color:var(--muted)}
 .done{display:none;font-size:11.5px;color:var(--ok);font-weight:600}.card.tagged{border-color:var(--ok)}.card.tagged .done{display:inline}
 .grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.grid .full{grid-column:1/-1}
 label{display:block;font-size:12px;color:var(--muted);margin-bottom:3px}
 input[type=text],textarea,select{width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--field);color:var(--ink);font:inherit;font-size:14px}
 textarea{resize:vertical;min-height:52px}
 .clarity-soft{color:var(--soft);font-weight:600}.clarity-blurry{color:var(--blur);font-weight:600}
 .empty{text-align:center;color:var(--muted);padding:50px 0}
 footer{text-align:center;color:var(--muted);font-size:12px;padding:24px}
 .saved{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);background:var(--ok);color:#fff;padding:8px 16px;border-radius:20px;font-size:13px;opacity:0;transition:opacity .3s;pointer-events:none}.saved.show{opacity:1}
</style></head><body>
<header>
 <h1>QABB — Image &amp; Map Tagging</h1>
 <div class="sub">Tags are pre-filled from the folder as a starting point — correct them per image. Add people, place, date, notes and a <b>clarity</b> rating. Entries autosave in this browser; click <b>Export</b> when done. You can also <b>Import clarity JSON</b> from the offline blur-scanner.</div>
 <div class="bar"><i id="prog"></i></div>
 <div class="controls">
  <input id="q" type="search" placeholder="Filter by file name, folder or event…">
  <label style="display:flex;gap:6px;align-items:center;color:var(--muted)"><input type="checkbox" id="untagged"> untagged only</label>
  <span id="count" class="sub"></span><span style="flex:1"></span>
  <button id="importClarity">Import clarity JSON…</button>
  <button id="import">Import tags…</button>
  <button id="csv">Export CSV</button>
  <button id="export" class="primary">Export JSON</button>
  <input id="file" type="file" accept="application/json" style="display:none">
  <input id="clarityFile" type="file" accept="application/json" style="display:none">
 </div>
</header>
<main id="list"></main>
<footer>__TOTAL__ images &middot; generated __GEN__. Nothing uploads automatically — export to save your work.</footer>
<div class="saved" id="toast">Saved</div>
<script>
const IMAGES=__DATA__;const KEY='qabb_tags_v1';const FIELDS=['event','people','place','date','clarity','notes'];
let store=JSON.parse(localStorage.getItem(KEY)||'{}');
// seed prefills once
IMAGES.forEach(im=>{if(!store[im.id]){store[im.id]={event:im.event||'',place:im.place||''};}});
localStorage.setItem(KEY,JSON.stringify(store));
const list=document.getElementById('list'),q=document.getElementById('q'),untagged=document.getElementById('untagged'),
 count=document.getElementById('count'),prog=document.getElementById('prog'),toast=document.getElementById('toast');
function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function isTagged(id){const r=store[id];return r&&['people','date','clarity','notes'].some(f=>(r[f]||'').trim())}
function thumb(id){return 'https://drive.google.com/thumbnail?id='+id+'&sz=w600'}
let tt;function flash(){toast.classList.add('show');clearTimeout(tt);tt=setTimeout(()=>toast.classList.remove('show'),900)}
function save(id,field,val){store[id]=store[id]||{};store[id][field]=val;localStorage.setItem(KEY,JSON.stringify(store));
 const c=document.querySelector('.card[data-id="'+CSS.escape(id)+'"]');if(c)c.classList.toggle('tagged',isTagged(id));updateProgress();flash()}
function updateProgress(){const done=IMAGES.filter(im=>isTagged(im.id)).length;prog.style.width=(IMAGES.length?done/IMAGES.length*100:0)+'%';count.textContent=done+' / '+IMAGES.length+' tagged'}
function claritySel(v){const opts=['','Clear','Slightly soft','Blurry'];return opts.map(o=>`<option value="${o}"${o===v?' selected':''}>${o||'— clarity —'}</option>`).join('')}
function render(){const term=q.value.trim().toLowerCase();list.innerHTML='';let shown=0;
 IMAGES.forEach(im=>{if(untagged.checked&&isTagged(im.id))return;
  if(term&&!((im.name+' '+im.folder+' '+(store[im.id]?.event||'')).toLowerCase().includes(term)))return;shown++;
  const r=store[im.id]||{};const card=document.createElement('div');card.className='card'+(isTagged(im.id)?' tagged':'');card.dataset.id=im.id;
  card.innerHTML=`<div><div class="thumb"><img loading="lazy" src="${thumb(im.id)}" alt="${esc(im.name)}"
    onerror="this.style.display='none';this.parentNode.insertAdjacentHTML('beforeend','<span class=sub style=padding:20px>Preview needs Drive sign-in</span>')">
    ${im.url?`<a class="open" href="${esc(im.url)}" target="_blank" rel="noopener">Open ↗</a>`:''}</div>
    <div class="fname" title="${esc(im.name)}">${esc(im.name)} <span class="done">✓ tagged</span></div>
    <div class="folder">📁 ${esc(im.folder)}</div><div class="folder">src: ${esc(im.original)}</div></div>
   <div class="grid">
    <div class="full"><label>Event / occasion</label><input type="text" data-f="event" value="${esc(r.event)}"></div>
    <div class="full"><label>People (comma-separated)</label><input type="text" data-f="people" value="${esc(r.people)}" placeholder="e.g. David Mitchell, Christine Mitchell"></div>
    <div><label>Place</label><input type="text" data-f="place" value="${esc(r.place)}"></div>
    <div><label>Date (approx ok)</label><input type="text" data-f="date" value="${esc(r.date)}" placeholder="e.g. 2016 or Jun 2017"></div>
    <div><label>Clarity</label><select data-f="clarity">${claritySel(r.clarity||'')}</select></div>
    <div><label>Clarity score (auto)</label><input type="text" data-f="clarity_score" value="${esc(r.clarity_score)}" placeholder="from offline scan" readonly></div>
    <div class="full"><label>Notes / description</label><textarea data-f="notes" placeholder="What is pictured, context, source…">${esc(r.notes)}</textarea></div>
   </div>`;
  card.querySelectorAll('[data-f]').forEach(el=>el.addEventListener('change',()=>save(im.id,el.dataset.f,el.value)));
  list.appendChild(card)});
 if(!shown)list.innerHTML='<div class="empty">Nothing matches this filter.</div>'}
document.getElementById('export').addEventListener('click',()=>{const rows=IMAGES.map(im=>Object.assign({id:im.id,name:im.name,original:im.original,folder:im.folder},store[im.id]||{}));download('QABB_image_tags.json',JSON.stringify(rows,null,2),'application/json')});
document.getElementById('csv').addEventListener('click',()=>{const head=['id','name','original','folder',...FIELDS,'clarity_score'];const q2=v=>'"'+String(v||'').replace(/"/g,'""')+'"';const lines=[head.join(',')];
 IMAGES.forEach(im=>{const r=store[im.id]||{};lines.push([im.id,im.name,im.original,im.folder,...FIELDS.map(f=>r[f]),r.clarity_score].map(q2).join(','))});download('QABB_image_tags.csv',lines.join('\n'),'text/csv')});
document.getElementById('import').addEventListener('click',()=>document.getElementById('file').click());
document.getElementById('file').addEventListener('change',e=>{const f=e.target.files[0];if(!f)return;const rd=new FileReader();
 rd.onload=()=>{try{JSON.parse(rd.result).forEach(row=>{if(row.id){store[row.id]=store[row.id]||{};FIELDS.forEach(k=>{if(row[k]!=null)store[row.id][k]=row[k]})}});localStorage.setItem(KEY,JSON.stringify(store));render();updateProgress();alert('Imported tags (merged).')}catch(err){alert('Could not read: '+err)}};rd.readAsText(f)});
document.getElementById('importClarity').addEventListener('click',()=>document.getElementById('clarityFile').click());
document.getElementById('clarityFile').addEventListener('change',e=>{const f=e.target.files[0];if(!f)return;const rd=new FileReader();
 rd.onload=()=>{try{const data=JSON.parse(rd.result);let byName={};IMAGES.forEach(im=>{byName[im.name]=im.id;byName[im.original]=im.id});let n=0;
   const arr=Array.isArray(data)?data:Object.entries(data).map(([k,v])=>({name:k,...(typeof v==='object'?v:{score:v})}));
   arr.forEach(row=>{const id=row.id||byName[row.name]||byName[row.file]||byName[row.filename];if(!id)return;store[id]=store[id]||{};
     const sc=row.score??row.clarity_score??row.variance;if(sc!=null){store[id].clarity_score=String(sc);
       if(!store[id].clarity){const s=+sc;store[id].clarity=s<55?'Blurry':s<140?'Slightly soft':'Clear'}}
     if(row.clarity)store[id].clarity=row.clarity;n++});
   localStorage.setItem(KEY,JSON.stringify(store));render();updateProgress();alert('Imported clarity for '+n+' images.')}catch(err){alert('Could not read: '+err)}};rd.readAsText(f)});
function download(name,text,type){const b=new Blob([text],{type});const u=URL.createObjectURL(b);const a=document.createElement('a');a.href=u;a.download=name;a.click();URL.revokeObjectURL(u)}
q.addEventListener('input',render);untagged.addEventListener('change',render);render();updateProgress();
</script></body></html>
"""

if __name__ == "__main__":
    main()
