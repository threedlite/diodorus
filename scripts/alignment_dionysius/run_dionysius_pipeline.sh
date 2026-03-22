#!/bin/bash
set -e
cd "$(dirname "$0")/../.."
source .venv/bin/activate

echo "=== Dionysius De Compositione Alignment Pipeline ==="
echo ""

echo "=== Step 1: Extract Perseus Greek ==="
python scripts/alignment_dionysius/01_extract_greek.py

echo ""
echo "=== Step 2: Extract Roberts English ==="
python scripts/alignment_dionysius/02_extract_english.py

echo ""
echo "=== Step 3: Embed & Align (Segmental DP) ==="
python scripts/alignment_dionysius/03_embed_and_align.py

echo ""
echo "=== Step 4: Validate with Entity Anchors ==="
python scripts/alignment_dionysius/04_entity_anchors.py

echo ""
echo "=== Step 5: Generate Outputs ==="
python scripts/alignment_dionysius/05_generate_outputs.py

echo ""
echo "=== Step 6: Quality Map ==="
python scripts/alignment_quality_map.py --prefix dionysius build/dionysius/entity_validated_alignments.json

echo ""
echo "=== Step 7: Integrity Check ==="
python scripts/verify_alignment_integrity.py dionysius

echo ""
echo "=== Step 8: Publish to final/ ==="
python scripts/publish_to_final.py dionysius build/dionysius/

echo ""
echo "=== Pipeline Complete ==="
echo "Outputs in ./build/dionysius/"
ls -la build/dionysius/
