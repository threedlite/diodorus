#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aristophanes_common import extract_english
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
extract_english('tlg005', PROJECT_ROOT / 'build' / 'aristophanes_peace' / 'english_sections.json', 'ogl-eng2')
