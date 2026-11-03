import os
import sys
from pathlib import Path

deps = Path(__file__).resolve().parent.parent / ".deps"
if deps.exists():
    sys.path.insert(0, str(deps))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.asgi import get_asgi_application

application = get_asgi_application()
