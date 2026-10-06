"""PARCHE CNTA (version local): arranque de Reporting en Windows, sin Docker ni bash.

Sustituye a entrypoint.sh: aplica las migraciones de alembic y arranca uvicorn,
solo en 127.0.0.1. Empaquetado con PyInstaller (sin consola). El directorio de
trabajo y la configuracion (REPORTING_*, PDF_DIRECTORY...) los fija el launcher.
"""
import os
import sys

FROZEN = getattr(sys, "frozen", False)
BASE = sys._MEIPASS if FROZEN else os.path.dirname(os.path.abspath(__file__))

# Sin consola, sys.stdout/stderr son None: se redirigen a un fichero para que
# ni uvicorn ni alembic fallen al escribir.
if sys.stdout is None or sys.stderr is None:
    os.makedirs("logs", exist_ok=True)
    _log = open(os.path.join("logs", "reporting.log"), "a", buffering=1, encoding="utf-8")
    sys.stdout = sys.stdout or _log
    sys.stderr = sys.stderr or _log

# El codigo importa sus modulos como `core`, `api`, `utils`...: app/ va en el path.
# (Empaquetado, PyInstaller ya los trae con pathex=app.)
if not FROZEN:
    sys.path.insert(0, os.path.join(BASE, "app"))

import uvicorn  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

from core.config import settings  # noqa: E402


def migrate() -> None:
    cfg = Config(os.path.join(BASE, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BASE, "alembic"))
    command.upgrade(cfg, "head")


if __name__ == "__main__":
    os.makedirs(os.path.join(settings.PDF_DIRECTORY, "livestock"), exist_ok=True)
    migrate()
    from main import app  # noqa: E402

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(settings.REPORTING_SERVICE_PORT),
        log_config=None,
    )
