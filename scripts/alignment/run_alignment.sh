#!/bin/bash
set -e
cd "$(dirname "$0")/../.."
source .venv/bin/activate

echo "=== Step 1: Extract Booth TEI ==="
python scripts/alignment/01_extract_booth.py

echo ""
echo "=== Step 2: Extract Perseus Greek ==="
python scripts/alignment/02_extract_perseus.py

echo ""
echo "=== Step 3: Normalise Booth English ==="
python scripts/alignment/03_normalise_booth.py

echo ""
echo "=== Step 4: Align Books ==="
python scripts/alignment/04_align_books.py

echo ""
echo "=== Step 5: Embed & Align Sections ==="
python scripts/alignment/05_embed_and_align.py

echo ""
echo "=== Step 6: Validate with Entity Anchors ==="
python scripts/alignment/06_entity_anchors.py

echo ""
echo "=== Step 7: Generate Outputs ==="
python scripts/alignment/07_generate_outputs.py

echo ""
echo "=== Step 8: Generate Perseus TEI Translation ==="
python scripts/alignment/08_generate_perseus_tei.py

echo ""
echo "Done. All outputs in ./output/"
ls -la output/
