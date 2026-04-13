# Use the local MiKTeX binaries directly so latexmk works from VS Code,
# the terminal, and any other caller without depending on PATH inheritance.
my $miktex_bin = 'C:/Users/ELITE/AppData/Local/Programs/MiKTeX/miktex/bin/x64';
$pdflatex = "$miktex_bin/pdflatex.exe -interaction=nonstopmode -synctex=1 %O %S";
$biber = "$miktex_bin/biber.exe %O %S";
