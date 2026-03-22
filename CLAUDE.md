never modify anything on the system or outside this folder.
only the user can run brew.
always use a venv and never run --break-system-packages
always be thoughtful, thorough, and truthful with yourself about what you did and didnt do
always document your plans in md files in the project
always update md doc files if something changes
dont be lazy; be thorough and careful
avoid quick fixes; make fixes as general as possible
never run rm -rf


## Project goal
Add English translations to ancient Greek works that currently only have Greek
text in Perseus and First1KGreek. We use Gutenberg and Wikisource as the source of public domain/CC-BY-SA
English translations to pair with Greek-only texts. Do NOT work on texts that
already have English in Perseus or First1KGreek — that is not the point.

## Alignment rules (NEVER BREAK)
1. All source text must appear in the output — no text may be skipped or dropped
2. All text must be in strict original order — no reordering ever
3. Alignment quality between Greek and English sections is best-effort — imprecise
   matches are acceptable, but every section of both source and target must be
   present and in order
4. The quality map must honestly report unmatched and low-confidence sections
