#!/usr/bin/env python3
"""Build QABB_documents_inventory.csv and image list from the on-disk enumeration.
Maps each file's parentId to a clean destination folder path (collapsing the
redundant zip-artifact double folder and dropping __MACOSX / junk)."""
import json, csv, sys, os

ENUM = sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude-0/-home-user-MCArchive/86d1fa9a-da03-5bca-b28a-0db92371dcef/scratchpad/qabb_work/enum_raw.json"
OUTDIR = os.path.dirname(os.path.abspath(__file__))

# parentId -> clean destination relative folder path
FOLDERS = {
    "1BhE4wg7xdI-llacdz3n4Wl8XIrkPmaHO": "QABB reference material CI OPRA",
    "1ymfYuPPr5Jw1x1hc1EdOFcrWA_1_o4ee": "QABB reference material CI OPRA",
    "1NtnJDI41CC8eTN6iWB2P6J501K87nOZy": "QABB reference material CI OPRA/QABB Ornithoptera alexandrae",
    "1zg4UrGd_gr6iPcap_utouFQt9rsXVwk5": "QABB reference material CI OPRA/QABB Ornithoptera alexandrae/1_QABB_Ornale",
    "1fDGSqtDZKlZ2pwJBan7GWB1aoC_-b0_o": "QABB reference material CI OPRA/QABB Ornithoptera alexandrae/2_Pararistolochia",
    "1FSVi4vM7ZueHuE4lyqWj44xysDP-EmDv": "QABB reference material CI OPRA/QABB Ornithoptera alexandrae/3_General",
    "1kSYrMaF44QgRcdEYkDxyaOz5LoV4PXKq": "QABB reference material CI OPRA/QABB Ornithoptera alexandrae/4_File 2-6-1 Correspondence",
    "1m0rsNZb4Z8xinEr8fl-Glnfug2WSxuhv": "QABB reference material CI OPRA/Other material",
    "1kIlzD46ixTpS0kJS1n2seEZPizKxlzES": "QABB references from Christine and David Mitchell",
}
# short prefix per folder for image filing names
PREFIX = {
    "QABB reference material CI OPRA/QABB Ornithoptera alexandrae/1_QABB_Ornale": "Ornale",
    "QABB reference material CI OPRA/QABB Ornithoptera alexandrae/2_Pararistolochia": "Parari",
    "QABB reference material CI OPRA/QABB Ornithoptera alexandrae/3_General": "General",
    "QABB reference material CI OPRA/QABB Ornithoptera alexandrae/4_File 2-6-1 Correspondence": "Corresp",
    "QABB reference material CI OPRA/QABB Ornithoptera alexandrae": "Ornale",
    "QABB reference material CI OPRA/Other material": "Other",
    "QABB reference material CI OPRA": "CIOPRA",
    "QABB references from Christine and David Mitchell": "Mitchell",
}
JUNK = {".DS_Store", "Thumbs.db"}
IMAGE_MIMES = {"image/jpeg", "image/png", "image/tiff", "image/bmp"}

data = json.load(open(ENUM))
files = [f for f in data["files"] if f["title"] not in JUNK and not f["title"].startswith("._")]

docs, imgs = [], []
for f in files:
    folder = FOLDERS.get(f["parentId"], "UNKNOWN:"+f["parentId"])
    rec = {
        "drive_id": f["id"], "title": f["title"], "mime": f["mimeType"],
        "ext": f.get("fileExtension",""), "size_bytes": f.get("fileSize",""),
        "folder": folder, "drive_url": f.get("viewUrl",""),
        "modified": f.get("modifiedTime",""),
    }
    (imgs if f["mimeType"] in IMAGE_MIMES else docs).append(rec)

# documents inventory
with open(os.path.join(OUTDIR,"QABB_documents_inventory.csv"),"w",newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=["folder","title","mime","ext","size_bytes","drive_id","drive_url","modified"])
    w.writeheader()
    for r in sorted(docs, key=lambda r:(r["folder"], r["title"].lower())):
        w.writerow({k:r[k] for k in w.fieldnames})

# image naming plan: <Prefix>_<NNN>.<ext>, running number per prefix
imgs_sorted = sorted(imgs, key=lambda r:(r["folder"], r["title"].lower()))
counters = {}
with open(os.path.join(OUTDIR,"QABB_image_naming_plan.csv"),"w",newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["filing_name","original_name","folder","drive_id","drive_url","size_bytes"])
    for r in imgs_sorted:
        pfx = PREFIX.get(r["folder"], "IMG")
        n = counters.get(pfx,0)+1; counters[pfx]=n
        ext = (r["ext"] or r["title"].rsplit(".",1)[-1]).lower()
        filing = f"QABB_{pfx}_{n:03d}.{ext}"
        w.writerow([filing, r["title"], r["folder"], r["drive_id"], r["drive_url"], r["size_bytes"]])

print(f"documents: {len(docs)}  images: {len(imgs)}")
print("docs by folder:")
from collections import Counter
for k,v in Counter(d["folder"] for d in docs).most_common():
    print(f"  {v:4d}  {k}")
print("images by folder:")
for k,v in Counter(i["folder"] for i in imgs).most_common():
    print(f"  {v:4d}  {k}")
