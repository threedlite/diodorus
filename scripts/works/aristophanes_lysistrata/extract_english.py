#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hickie_extract_play import extract_play, PROJECT_ROOT
volume = PROJECT_ROOT / "data-sources" / "english_trans-dev" / "volumes" / "aristophanes_2_1853" / "aristophanes_2_1853.xml"
output = PROJECT_ROOT / "build" / "aristophanes_lysistrata" / "english_sections.json"
extract_play(volume, "LYSISTRATA", output)
