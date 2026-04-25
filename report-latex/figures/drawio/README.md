# draw.io Sources for Report Diagrams

This folder stores the active editable source files for the report diagrams.

## Workflow

1. Edit `.drawio` files in this folder.
2. Export each diagram to `PDF` in `report-latex/figures/` using the same base filename.
3. Keep LaTeX labels unchanged and include the exported files in chapter figures.

## Naming map

- `database_auth_erd.drawio` -> `report-latex/figures/database_auth_erd.pdf`
- `database_core_erd.drawio` -> `report-latex/figures/database_core_erd.pdf`
- `global_use_case.drawio` -> `report-latex/figures/global_use_case.pdf`
- `sprint1_activity.drawio` -> `report-latex/figures/sprint1_activity.pdf`
- `sprint1_sequence.drawio` -> `report-latex/figures/sprint1_sequence.pdf`
- `sprint2_component.drawio` -> `report-latex/figures/sprint2_component.pdf`
- `sprint2_sequence.drawio` -> `report-latex/figures/sprint2_sequence.pdf`
- `sprint3_component.drawio` -> `report-latex/figures/sprint3_component.pdf`
- `sprint3_sequence.drawio` -> `report-latex/figures/sprint3_sequence.pdf`
- `sprint4_frontend_arch.drawio` -> `report-latex/figures/sprint4_frontend_arch.pdf`  # alert workflow diagram

## Removed legacy sources

The old sprint 1 use-case file and the sprint 2/3 data-flow files were removed when the sprint structure was simplified. The old sprint 5/6 sources were also deleted so the editable set now matches the four-sprint report structure.
