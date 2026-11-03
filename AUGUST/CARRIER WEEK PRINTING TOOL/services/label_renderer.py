"""Render high-resolution labels with Pillow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


class LabelTemplateError(FileNotFoundError):
    pass


class LabelRenderer:
    def __init__(self, template_path: Path, fonts_dir: Path, config: dict[str, Any]) -> None:
        self.template_path = template_path
        self.fonts_dir = fonts_dir
        self.config = config

    def _font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        candidates = [self.fonts_dir / "DejaVuSans-Bold.ttf", Path("C:/Windows/Fonts/arialbd.ttf")]
        for candidate in candidates:
            if candidate.exists():
                return ImageFont.truetype(str(candidate), size=size)
        try:
            return ImageFont.truetype("DejaVuSans-Bold.ttf", size=size)
        except OSError:
            return ImageFont.load_default()

    def _fit_font(self, draw: ImageDraw.ImageDraw, text: str, size: int, max_width: int, minimum: int = 12):
        font = self._font(size)
        while size > minimum and draw.textbbox((0, 0), text, font=font)[2] > max_width:
            size -= 1
            font = self._font(size)
        return font

    def _wrap_two_lines(self, draw: ImageDraw.ImageDraw, text: str, size: int, max_width: int):
        font = self._font(size)
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return [text], font
        words = text.split()
        best: tuple[list[str], Any] | None = None
        for split in range(1, len(words)):
            lines = [" ".join(words[:split]), " ".join(words[split:])]
            fitted = self._fit_font(draw, max(lines, key=len), size, max_width)
            width = max(draw.textbbox((0, 0), line, font=fitted)[2] for line in lines)
            if width <= max_width:
                score = abs(draw.textbbox((0, 0), lines[0], font=fitted)[2] - draw.textbbox((0, 0), lines[1], font=fitted)[2])
                if best is None or score < best[1]:
                    best = (lines, score, fitted)
        return (best[0], best[2]) if best else ([text], self._fit_font(draw, text, size, max_width))

    @staticmethod
    def split_full_name(full_name: str) -> tuple[str, str]:
        """Split a full name so the surname begins at the second space.
        """
        words = full_name.split()
        if len(words) >= 3:
            return " ".join(words[:2]), " ".join(words[2:])
        if len(words) == 2:
            return words[0], words[1]
        return (words[0], "") if words else ("", "")
    @staticmethod
    def split_career(career: str) -> tuple[str, str]:
        words = career.split()
        if len(words) >= 2:
            return " ".join(words[:2]), " ".join(words[2:])
        if len(words) == 1:
            return (words[0],"")
        return (words[0], "") if words else ("", "")

    def render(self, student: dict[str, Any]) -> Image.Image:
        label = self.config["label"]
        size = (int(label["width_px"]), int(label["height_px"]))
        if not self.template_path.exists():
            raise LabelTemplateError(f"Label template not found:\n{self.template_path}")
        image = Image.open(self.template_path).convert("RGB").resize(size, Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(image)
        full_name = str(student.get("Nombre completo", student.get("Nombre", "")))
        name, last_name = self.split_full_name(full_name)
        careerfull = str(student.get("Carrera", ""))
        career1, career2 = self.split_career(careerfull)
        semester_value = str(student.get("Semestre", ""))
        folio_value = str(student.get("UniqueID", ""))
        semester = f"{semester_value} SEMESTRE" if semester_value else ""

        name_cfg = label["name"]
        name_font = self._fit_font(draw, name, int(name_cfg["font_size"]), int(name_cfg["max_width"]))
        draw.text((int(name_cfg["x"]), int(name_cfg["y"])), name, font=name_font, fill="black", anchor="mm", align="center")

        last_name_cfg = label["last_name"]
        last_name_font = self._fit_font(
            draw,
            last_name,
            int(last_name_cfg["font_size"]),
            int(last_name_cfg["max_width"]),
        )
        draw.text(
            (int(last_name_cfg["x"]), int(last_name_cfg["y"])),
            last_name,
            font=last_name_font,
            fill="black",
            anchor="mm",
            align="center",
        )

        career1_cfg = label["career1"]
        career2_cfg = label["career2"]
        career1_font = self._fit_font(draw,career1,int(career1_cfg["font_size"]), int(career1_cfg["max_width"]),)
        career2_font = self._fit_font(draw,career2,int(career2_cfg["font_size"]), int(career2_cfg["max_width"]),)
        draw.text((int(career1_cfg["x"]), int(career1_cfg["y"])), career1, font=career1_font, fill="black", anchor="mm", align="center",)
        draw.text((int(career2_cfg["x"]), int(career2_cfg["y"])), career2, font=career2_font, fill="black", anchor="mm", align="center",)

        semester_cfg = label["semester"]
        semester_font = self._fit_font(draw, semester, int(semester_cfg["font_size"]), int(semester_cfg["max_width"]))
        draw.text((int(semester_cfg["x"]), int(semester_cfg["y"])), semester, font=semester_font, fill="black", anchor="mm", align="center")
        folio_cfg = label["folio"]
        folio_font = self._fit_font(draw, folio_value, int(folio_cfg["font_size"]), int(folio_cfg["max_width"]))
        draw.text((int(folio_cfg["x"]), int(folio_cfg["y"])), folio_value, font=folio_font, fill="black", anchor="mm", align="center")
        return image
