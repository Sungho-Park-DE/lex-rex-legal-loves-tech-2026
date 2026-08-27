"""Markdown -> PDF für die Team-Unterlagen (Aufgabenpakete, Briefings).

Kein Produktcode. Ersetzt den Obsidian-Export, wenn ein Paket in einer Session
fertig wird: A4, Tabellen mit Rahmen, deutsche Anführungszeichen, Seitenzahlen.

    .venv/bin/python tools/md2pdf.py analysis/12_aufgaben_franz_runde3_de.md ~/Downloads/Franz_Runde3.pdf

Braucht `markdown` und `xhtml2pdf` im venv (beides reines Python, keine
Systembibliotheken). pandoc/weasyprint/Chrome sind auf der Mac mini nicht
installiert, deshalb dieser Weg.
"""
import sys
import re
import pathlib
import markdown
from xhtml2pdf import pisa

src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
md = src.read_text(encoding="utf-8")

# deutsche Anführungszeichen schließen: „... "  ->  „..."
def close_quotes(t):
    res, i = [], 0
    while True:
        j = t.find("„", i)
        if j < 0:
            res.append(t[i:])
            break
        k = t.find('"', j)
        if k < 0:
            res.append(t[i:])
            break
        res.append(t[i:k])
        res.append("“")
        i = k + 1
    return "".join(res)
md = close_quotes(md)

body = markdown.markdown(md, extensions=["tables", "sane_lists"])

# Fußzeile aus der ersten H1: alles vor dem Doppelpunkt, sonst der Dateiname
m = re.search(r"^#\s+(.+)$", md, re.M)
kopfzeile = (m.group(1).split(":")[0].strip() if m else src.stem)


CSS = """
@page { size: a4 portrait; margin: 1.6cm 1.5cm 1.7cm 1.5cm;
        @frame footer { -pdf-frame-content: ftr; bottom: 0.8cm; left: 1.5cm;
                        width: 18cm; height: 0.8cm; } }
body { font-family: helvetica; font-size: 9.6pt; line-height: 1.38; color: #1a1a1a; }
h1 { font-size: 17pt; margin: 0 0 4pt 0; color: #000; }
h2 { font-size: 12pt; margin: 15pt 0 4pt 0; color: #000;
     border-bottom: 0.7pt solid #999; padding-bottom: 2pt; }
h3 { font-size: 10.5pt; margin: 11pt 0 3pt 0; }
p  { margin: 4pt 0; }
ul, ol { margin: 4pt 0 4pt 14pt; }
li { margin: 1.5pt 0; }
blockquote { margin: 7pt 0; padding: 6pt 8pt; background-color: #f2f2f2;
             border-left: 2pt solid #777; }
blockquote p { margin: 2.5pt 0; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 8pt 0; }
th, td { border: 0.6pt solid #8a8a8a; padding: 3pt 4.5pt; text-align: left;
         vertical-align: top; font-size: 8.6pt; line-height: 1.3; }
th { background-color: #e6e6e6; }
code { font-family: courier; font-size: 8.4pt; background-color: #eeeeee; }
strong, b, th { font-weight: bold; }
em, i { font-style: italic; }
#ftr { text-align: right; font-size: 7.5pt; color: #777; }
"""

html = ("<html><head><meta charset='utf-8'><style>" + CSS + "</style></head><body>"
        + body
        + f"<div id='ftr'>Fall-Prüfer · {kopfzeile} · "
          "Seite <pdf:pagenumber> von <pdf:pagecount></div>"
        + "</body></html>")

with open(out, "wb") as fh:
    res = pisa.CreatePDF(html, dest=fh, encoding="utf-8")
print("errors:", res.err, "->", out, out.stat().st_size, "bytes")
