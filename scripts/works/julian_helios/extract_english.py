#!/usr/bin/env python3
"""Extract English hymn from eng_trans-dev julian_1888 volume."""
import json, re
from pathlib import Path
from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INPUT_DIR = PROJECT_ROOT / "data-sources" / "english_trans-dev" / "volumes" / "julian_1888"
OUTPUT = PROJECT_ROOT / "build" / "julian_helios" / "english_sections.json"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

xml_path = sorted(INPUT_DIR.glob("*.xml"))[0]
tree = etree.parse(str(xml_path))
root = tree.getroot()
TEI_NS = "http://www.tei-c.org/ns/1.0"

def extract_p_text(p):
    parts = []
    if p.text: parts.append(p.text)
    for child in p:
        tag = etree.QName(child.tag).localname if isinstance(child.tag, str) else ""
        if tag in ("note", "figure", "pb", "foreign"): pass
        elif tag == "lb": parts.append(" ")
        else: parts.append("".join(child.itertext()))
        if child.tail: parts.append(child.tail)
    return re.sub(r'\s+', ' ', "".join(parts).replace("\xad", "")).strip()

body = root.find(f".//{{{TEI_NS}}}body")
edition_div = body.find(f"{{{TEI_NS}}}div") or body

in_hymn = False
all_sections = []
pi = 0

for div in edition_div:
    tag = etree.QName(div.tag).localname if isinstance(div.tag, str) else ""
    if tag != "div": continue
    titles = [(t.text or "").strip().upper() for t in div.findall(f".//{{{TEI_NS}}}title")]
    if any("SOVEREIGN SUN" in t for t in titles):
        in_hymn = True
    if in_hymn and any("MOTHER OF THE GODS" in t for t in titles):
        break
    if not in_hymn: continue
    for p in div.findall(f"{{{TEI_NS}}}p"):
        text = extract_p_text(p)
        if len(text) >= 20:
            pi += 1
            all_sections.append({
                "book": "1", "section": str(pi),
                "cts_ref": f"1.{pi}", "text": text, "char_count": len(text),
            })

print(f"Extracted {len(all_sections)} English sections")
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": all_sections}, f, ensure_ascii=False, indent=2)
print(f"Saved: {OUTPUT}")
