Place image files used by the LaTeX report in this folder.

Suggested filenames (referenced in chapters):
- architecture_diagram.png  # system architecture overview
- sample_frame_detection.png # example video frame with detections
- evaluation_plot_waittime.png # evaluation metric plots

Notes:
- Preferred formats: PNG, PDF, or JPG. PDF is recommended for vector diagrams.
- To generate a quick placeholder, create a simple PNG of size 1200x800 with any image editor.
- After adding images, re-run `latexmk -pdf main.tex` in the `report-latex` folder.
