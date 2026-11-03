"""Render the existing IP brand mark into Windows icon sizes."""
from pathlib import Path
import os
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[1]
target = root / 'build-resources'
target.mkdir(exist_ok=True)
image = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((0, 0, 255, 255), radius=64, fill='#112E51')
fontfile = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'segoeuib.ttf'
font = ImageFont.truetype(str(fontfile), 114) if fontfile.exists() else ImageFont.load_default(size=114)
draw.text((128, 121), 'IP', font=font, fill='white', anchor='mm')
image.save(target / 'icon.png')
image.save(target / 'icon.ico', sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
