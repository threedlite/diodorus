#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aristophanes_common import extract_greek
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
extract_greek('tlg011', PROJECT_ROOT / 'build' / 'aristophanes_plutus' / 'greek_sections.json')
