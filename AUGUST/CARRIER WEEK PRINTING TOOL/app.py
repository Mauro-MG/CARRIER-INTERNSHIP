from __future__ import annotations
import logging
import shutil
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

def configure_logging(root: Path) -> None:
    (root / "logs").mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(root / "logs" / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])

def main() -> None:
    resource_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    root_path = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else resource_path
    bundled_config = resource_path / "config.json"
    local_config = root_path / "config.json"
    if not local_config.exists() and bundled_config.exists() and bundled_config != local_config:
        shutil.copy2(bundled_config, local_config)
    configure_logging(root_path)
    try:
        import ttkbootstrap as ttk
        from services.config_service import ConfigService
        from services.database_service import DatabaseService
        from ui.main_window import MainWindow

        config = ConfigService(root_path)
        config.initialize()
        DatabaseService(root_path / "database" / "students.xlsx").initialize()
        window = ttk.Window(themename="cosmo")
        window.title("Student Label Printer")
        window.geometry("1180x720")
        window.minsize(940, 580)
        MainWindow(window, root_path, config, resource_path)
        window.mainloop()
    except Exception:
        logging.getLogger(__name__).exception("Fatal startup error")
        raise

if __name__ == "__main__":
    main()
