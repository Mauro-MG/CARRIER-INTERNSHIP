"""Windows printer enumeration and bitmap submission."""
from __future__ import annotations
import sys
from PIL import Image, ImageWin

class PrinterError(RuntimeError):
    """A user-facing printer failure."""

class PrinterService:
    @staticmethod
    def _modules():
        if sys.platform != "win32":
            raise PrinterError("Direct printing is only supported on Windows.")
        try:
            import win32con, win32print, win32ui
        except ImportError as exc:
            raise PrinterError("pywin32 is not installed. Run: pip install pywin32") from exc
        return win32con, win32print, win32ui

    def list_printers(self) -> list[str]:
        _, win32print, _ = self._modules()
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        return sorted({item[2] for item in win32print.EnumPrinters(flags)})

    def is_available(self, name: str) -> bool:
        return bool(name) and name in self.list_printers()

    def print_image(self, image: Image.Image, printer_name: str) -> None:
        win32con, _, win32ui = self._modules()
        if not printer_name:
            raise PrinterError("No printer is configured. Open Printer Settings first.")
        if printer_name not in self.list_printers():
            raise PrinterError(f"The configured printer is unavailable:\n{printer_name}")
        dc = win32ui.CreateDC()
        started = False
        try:
            dc.CreatePrinterDC(printer_name)
            page_w, page_h = dc.GetDeviceCaps(win32con.HORZRES), dc.GetDeviceCaps(win32con.VERTRES)
            scale = min(page_w / image.width, page_h / image.height)
            width, height = int(image.width * scale), int(image.height * scale)
            x, y = (page_w - width) // 2, (page_h - height) // 2
            dc.StartDoc("Student Label")
            started = True
            dc.StartPage()
            ImageWin.Dib(image.convert("RGB")).draw(dc.GetHandleOutput(), (x, y, x + width, y + height))
            dc.EndPage()
            dc.EndDoc()
        except Exception as exc:
            if started:
                try: dc.AbortDoc()
                except Exception: pass
            raise PrinterError(f"Windows could not submit the print job.\n\n{exc}") from exc
        finally:
            dc.DeleteDC()
