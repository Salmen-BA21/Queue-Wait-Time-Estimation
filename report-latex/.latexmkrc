# Use tools from PATH to keep this config portable across machines.
$pdflatex = 'pdflatex -interaction=nonstopmode -synctex=1 %O %S';

# Use biber from PATH.
$biber = 'biber %O %S';
