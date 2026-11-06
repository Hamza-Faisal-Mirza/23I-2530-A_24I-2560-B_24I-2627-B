"""Render approach.md -> approach_note.pdf and proposal.md -> proposal.pdf.

    python tools/build_docs.py

A small Markdown subset is supported: '#'/'##' headings, paragraphs, '- '
bullets, pipe tables (widths via '<!-- widths: ... -->'), '<!-- pagebreak -->',
**bold** and `code`. The font size is reduced step by step until the document
fills exactly two pages, as the project statement requires.
"""
import io
import os
import re
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = "Helvetica"


def register_fonts():
    global FONT
    fdir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    files = {"Arial": "arial.ttf", "Arial-Bold": "arialbd.ttf",
             "Arial-Italic": "ariali.ttf", "Arial-BoldItalic": "arialbi.ttf"}
    if all(os.path.exists(os.path.join(fdir, f)) for f in files.values()):
        for name, f in files.items():
            pdfmetrics.registerFont(TTFont(name, os.path.join(fdir, f)))
        addMapping("Arial", 0, 0, "Arial")
        addMapping("Arial", 1, 0, "Arial-Bold")
        addMapping("Arial", 0, 1, "Arial-Italic")
        addMapping("Arial", 1, 1, "Arial-BoldItalic")
        FONT = "Arial"


def inline(text):
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`(.+?)`", r'<font face="Courier">\1</font>', text)
    return text


def parse(md):
    """-> (title, blocks) with blocks of kind h2/p/bullet/table/pagebreak."""
    title, blocks, widths = None, [], None
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln:
            i += 1
            continue
        if ln.startswith("<!-- widths:"):
            widths = [float(x) for x in ln[len("<!-- widths:"):-3].split(",")]
        elif ln.startswith("<!-- pagebreak"):
            blocks.append(("pagebreak", None))
        elif ln.startswith("# "):
            title = ln[2:]
        elif ln.startswith("## "):
            blocks.append(("h2", ln[3:]))
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            blocks.append(("table", (rows, widths)))
            widths = None
            continue
        elif ln.startswith("- "):
            blocks.append(("bullet", ln[2:]))
        else:
            blocks.append(("p", ln))
        i += 1
    return title, blocks


def build(md_path, pdf_path, pagesize, size, margin, title_in_body):
    title, blocks = parse(open(md_path, encoding="utf-8").read())
    lead = size * 1.18
    body = ParagraphStyle("body", fontName=FONT, fontSize=size, leading=lead, alignment=TA_LEFT,
                          spaceAfter=size * 0.35)
    cell = ParagraphStyle("cell", parent=body, spaceAfter=0)
    head = ParagraphStyle("head", parent=body, fontName=FONT + "-Bold" if FONT == "Arial" else "Helvetica-Bold",
                          fontSize=size * 1.25, leading=size * 1.5, spaceBefore=size * 0.5,
                          spaceAfter=size * 0.3)
    ttl = ParagraphStyle("ttl", parent=head, fontSize=size * 1.6, leading=size * 1.9, spaceBefore=0)
    bullet = ParagraphStyle("bullet", parent=body, leftIndent=size * 1.2, bulletIndent=size * 0.3,
                            spaceAfter=size * 0.2)
    W = pagesize[0] - 2 * margin
    story = []
    if title_in_body and title:
        story.append(Paragraph(inline(title), ttl))
    for kind, val in blocks:
        if kind == "h2":
            story.append(Paragraph(inline(val), head))
        elif kind == "p":
            story.append(Paragraph(inline(val), body))
        elif kind == "bullet":
            story.append(Paragraph(inline(val), bullet, bulletText="\u2022"))
        elif kind == "pagebreak":
            story.append(PageBreak())
        elif kind == "table":
            rows, widths = val
            ncol = len(rows[0])
            widths = widths or [1.0 / ncol] * ncol
            data = [[Paragraph(("<b>%s</b>" % inline(c)) if r == 0 else inline(c), cell) for c in row]
                    for r, row in enumerate(rows)]
            t = Table(data, colWidths=[w * W for w in widths], repeatRows=1)
            t.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#555555")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDE4EE")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2.5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2.5),
                ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            story.append(t)
            story.append(Spacer(1, size * 0.4))
    pages = [0]

    def on_page(canv, doc):
        pages[0] = doc.page
        canv.saveState()
        canv.setFont(FONT, 7)
        canv.setFillColor(colors.HexColor("#444444"))
        if not title_in_body and title:
            canv.drawString(margin, pagesize[1] - margin * 0.6, title)
        canv.drawRightString(pagesize[0] - margin, margin * 0.45, f"Page {doc.page} of 2")
        canv.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=pagesize, leftMargin=margin, rightMargin=margin,
                            topMargin=margin, bottomMargin=margin, title=title or "",
                            author="Group 76: Hamza Faisal, Ahmed Hassan, Zeyan Ahmed")
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return pages[0], buf.getvalue()


def fit(md, pdf, pagesize, margin, title_in_body, start):
    size = start
    while size > 5.0:
        n, data = build(os.path.join(ROOT, md), None, pagesize, size, margin, title_in_body)
        if n <= 2:
            if n == 2 or True:
                with open(os.path.join(ROOT, pdf), "wb") as fh:
                    fh.write(data)
                print(f"{pdf}: {n} pages at {size:.2f} pt")
                return n
        size -= 0.1
    raise SystemExit(f"{md} does not fit on two pages")


def main():
    register_fonts()
    n1 = fit("approach.md", "approach_note.pdf", A4, 1.2 * cm, True, 9.0)
    n2 = fit("proposal.md", "proposal.pdf", landscape(A4), 0.9 * cm, False, 9.0)
    if n1 != 2 or n2 != 2:
        print("warning: a document has fewer than two pages", file=sys.stderr)


if __name__ == "__main__":
    main()
