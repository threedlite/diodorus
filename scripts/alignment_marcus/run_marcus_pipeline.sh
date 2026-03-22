#!/bin/bash
set -e
cd "$(dirname "$0")/../.."
source .venv/bin/activate

echo "=== Marcus Aurelius Alignment Pipeline ==="
echo ""

echo "=== Step 1: Extract Perseus Greek ==="
python scripts/alignment_marcus/01_extract_greek.py

echo ""
echo "=== Step 2: Extract Long English ==="
python scripts/alignment_marcus/02_extract_english.py

echo ""
echo "=== Step 3: Embed & Align (Segmental DP) ==="
python scripts/alignment_marcus/03_embed_and_align.py

echo ""
echo "=== Step 4: Validate with Entity Anchors ==="
python scripts/alignment_marcus/04_entity_anchors.py

echo ""
echo "=== Step 5: Generate Outputs ==="
python scripts/alignment_marcus/05_generate_outputs.py

echo ""
echo "=== Step 6: Quality Map ==="
python scripts/alignment_quality_map.py --prefix marcus build/marcus/entity_validated_alignments.json

echo ""
echo "=== Step 7: Integrity Check ==="
python scripts/verify_alignment_integrity.py marcus

echo ""
echo "=== Step 8: Publish to final/ ==="
python scripts/publish_to_final.py marcus build/marcus/

echo ""
echo "=== Pipeline Complete ==="
echo "Outputs in ./build/marcus/"
ls -la build/marcus/
