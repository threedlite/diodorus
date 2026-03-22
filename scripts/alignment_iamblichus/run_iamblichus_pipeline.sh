#!/bin/bash
set -e
cd "$(dirname "$0")/../.."
source .venv/bin/activate

echo "=== Iamblichus Alignment Pipeline ==="
echo ""

echo "=== Step 1: Extract Greek from First1KGreek ==="
python scripts/alignment_iamblichus/01_extract_greek.py

echo ""
echo "=== Step 2: Extract English from Gutenberg ==="
python scripts/alignment_iamblichus/02_extract_english.py

echo ""
echo "=== Step 3: Embed & Align (Segmental DP) ==="
python scripts/alignment_iamblichus/03_embed_and_align.py

echo ""
echo "=== Step 4: Validate with Entity Anchors ==="
python scripts/alignment_iamblichus/04_entity_anchors.py

echo ""
echo "=== Step 5: Generate Outputs ==="
python scripts/alignment_iamblichus/05_generate_outputs.py

echo ""
echo "=== Step 6: Quality Map ==="
python scripts/alignment_quality_map.py --prefix iamblichus build/iamblichus/entity_validated_alignments.json

echo ""
echo "=== Step 7: Integrity Check ==="
python scripts/verify_alignment_integrity.py iamblichus

echo ""
echo "=== Step 8: Publish to final/ ==="
python scripts/publish_to_final.py iamblichus build/iamblichus/

echo ""
echo "=== Pipeline Complete ==="
echo "Outputs in ./build/iamblichus/"
ls -la build/iamblichus/
