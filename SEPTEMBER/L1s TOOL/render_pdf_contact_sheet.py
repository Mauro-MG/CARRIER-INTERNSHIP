import sys
from pathlib import Path
from pdf2image import convert_from_path
from PIL import Image, ImageDraw, ImageFont

pdf_dir = Path(sys.argv[1]).resolve()
out_dir = Path(sys.argv[2]).resolve()
out_dir.mkdir(parents=True, exist_ok=True)
poppler = r"C:\Users\montelma1\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin"

thumbs = []
for pdf in sorted(pdf_dir.glob("*.pdf")):
    pages = convert_from_path(str(pdf), dpi=90, first_page=1, last_page=1, poppler_path=poppler)
    if not pages:
        continue
    img = pages[0].convert("RGB")
    img.thumbnail((520, 680))
    canvas = Image.new("RGB", (540, 730), "white")
    canvas.paste(img, ((540-img.width)//2, 35))
    draw = ImageDraw.Draw(canvas)
    draw.text((10, 8), pdf.stem, fill="black")
    target = out_dir / f"{pdf.stem}.png"
    canvas.save(target)
    thumbs.append(canvas)

cols = 3
rows = (len(thumbs) + cols - 1) // cols
sheet = Image.new("RGB", (cols*540, rows*730), (225,225,225))
for i, img in enumerate(thumbs):
    sheet.paste(img, ((i % cols)*540, (i // cols)*730))
sheet.save(out_dir / "all_sheets_contact.png")
print(out_dir / "all_sheets_contact.png")
