#!/bin/bash
set -e
cd "$(dirname "$0")/../.."
source .venv/bin/activate

echo "=== Aesop Fables Alignment Pipeline ==="
echo ""

echo "=== Step 1: Extract Greek Fables from First1KGreek ==="
python scripts/alignment_aesop/01_extract_greek_fables.py

echo ""
echo "=== Step 2: Extract English Fables from Gutenberg ==="
python scripts/alignment_aesop/02_extract_english_fables.py

echo ""
echo "=== Step 3: Pairwise Embed & Match ==="
python scripts/alignment_aesop/03_pairwise_embed_and_match.py

echo ""
echo "=== Step 4: Validate with Entity Anchors ==="
python scripts/alignment_aesop/04_entity_anchors.py

echo ""
echo "=== Step 5: Generate Outputs ==="
python scripts/alignment_aesop/05_generate_outputs.py

echo ""
echo "=== Step 6: Quality Map ==="
python scripts/alignment_quality_map.py --prefix aesop build/aesop/entity_validated_alignments.json

echo ""
echo "=== Step 7: Integrity Check ==="
python scripts/verify_alignment_integrity.py aesop

echo ""
echo "=== Step 8: Publish to final/ ==="
python scripts/publish_to_final.py aesop build/aesop/

echo ""
echo "=== Pipeline Complete ==="
echo "Outputs in ./build/aesop/"
ls -la build/aesop/
