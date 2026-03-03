#!/bin/bash
set -e
cd "$(dirname "$0")/../.."
source .venv/bin/activate

echo "=== Statius Alignment Pipeline ==="
echo ""

echo "=== Step 1: Fetch Mozley English from Theoi.com ==="
python scripts/alignment_statius/01_scrape_mozley.py

echo ""
echo "=== Step 2: Extract Latin Verse from Perseus TEI ==="
python scripts/alignment_statius/02_extract_latin_tei.py

echo ""
echo "=== Step 3: Normalise Mozley English ==="
python scripts/alignment_statius/03_normalise_mozley.py

echo ""
echo "=== Step 4: Segment Latin Lines into Passages ==="
python scripts/alignment_statius/04_segment_latin_lines.py

echo ""
echo "=== Step 5: Align Books ==="
python scripts/alignment_statius/05_align_books.py

echo ""
echo "=== Step 6: Embed & Align (Segmental DP) ==="
python scripts/alignment_statius/06_embed_and_align.py

echo ""
echo "=== Step 7: Validate with Entity Anchors ==="
python scripts/alignment_statius/07_entity_anchors.py

echo ""
echo "=== Step 8: Generate Final Outputs ==="
python scripts/alignment_statius/08_generate_outputs.py

echo ""
echo "=== Pipeline Complete ==="
echo "Outputs in ./output/statius/"
ls -la output/statius/
