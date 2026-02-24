# Use MiKTeX pdflatex explicitly so latexmk finds it even if PATH differs
$pdflatex = '"C:/Users/ELITE/AppData/Local/Programs/MiKTeX/miktex/bin/x64/pdflatex.exe" -interaction=nonstopmode -synctex=1 %O %S';

# Use MiKTeX biber explicitly
$biber = '"C:/Users/ELITE/AppData/Local/Programs/MiKTeX/miktex/bin/x64/biber.exe" %O %S';
