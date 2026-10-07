# ANNA 1.0.0 source cleanup report

This directory is a cleaned copy of the supplied ANNA development tree. The original archive was not modified.

## Removed generated/local artefacts

- `build/`
- `dist/`
- `.pytest_cache/`
- all `__pycache__/` and compiled Python cache files
- `results/` development/session output
- local `anna_data/` and `emma_data/`
- the previously generated `ANNA-1.0.0-Windows.zip`

## Removed obsolete/duplicate legacy files

- `Emma.spec` (superseded by `ANNA.spec`)
- `assets/app/Emma.ico` and `assets/app/Emma.png` (duplicate legacy-branded assets)
- `tests/test_emma_1_0_closure.py` (superseded by `test_anna_1_0_closure.py`)
- `tests/test_step39c_emma_data_migration.py` (superseded by `test_step39c_anna_data_migration.py`, which also tests Emma-data migration)
- stale demonstration images under `demo_project/assets/` that are not referenced by the current `washing_hands.json` sample
- the previous soap support image of uncertain provenance

## Updated

- `demo_project/washing_hands.json`: current project identity changed from `emma-interactive-video` to `anna-interactive-video`.
- demonstration README, licence note, and manual-validation checklist updated to describe the current ANNA Washing Hands sample rather than an obsolete Emma spreadsheet demo.
- demonstration media licensing documented for public release: the two original demonstration videos are distributed under CC BY 4.0.
- the previous soap support image of uncertain provenance was replaced with an image generated using OpenAI image generation specifically for the ANNA demonstration project.
- root `README.md` and `RESOURCE_INVENTORY.md` updated for the ANNA 1.0.0 public release.

## Deliberately retained legacy references

References to `emma_data`, `lola_data`, and `%LOCALAPPDATA%\\Emma` remain where they implement or test backwards-compatible migration to ANNA. `.gitignore` also retains legacy data-directory names so that local legacy data cannot be committed accidentally.

## Public release status

The licensing status of the demonstration media has been resolved for the public release. The two demonstration videos are original works created by the ANNA authors and are distributed under the Creative Commons Attribution 4.0 International (CC BY 4.0) licence. The soap image used as a visual support was generated using OpenAI image generation specifically for the ANNA demonstration project. Full provenance and licensing information is provided in `RESOURCE_INVENTORY.md` and `demo_project/LICENSES_DEMO.md`.

The full automated test suite was run on the cleaned source, with all 312 tests passing. A Windows executable/package was subsequently rebuilt from the cleaned source and confirmed to start correctly.