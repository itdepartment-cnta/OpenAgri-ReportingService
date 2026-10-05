"""Borrado periodico de los PDF generados.

PARCHE CNTA. Upstream guarda cada informe para siempre en PDF_DIRECTORY, sin
ninguna limpieza. Aqui los informes se descargan nada mas generarse y no
interesa conservarlos, asi que se borran pasado un tiempo.

Se activa con REPORTING_PDF_RETENTION_HOURS > 0. Con 0 (el valor por defecto)
no se borra nada, que es el comportamiento original.
"""

import asyncio
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Solo se borra lo que genera este servicio. Cualquier otro fichero que alguien
# deje en la carpeta no se toca.
EXTENSIONES = (".pdf", ".pdf.tmp", ".error")


def delete_old_reports(
    directory: str, max_age_seconds: float, now: Optional[float] = None
) -> int:
    """Borra los informes de `directory` (recursivo) mas viejos que `max_age_seconds`.

    Devuelve cuantos ficheros borro. No sigue enlaces simbolicos, no toca
    ficheros con otras extensiones, quita las carpetas que queden vacias (nunca
    la raiz) y se niega a trabajar sobre la raiz del sistema de ficheros.
    """
    if not directory or not os.path.isdir(directory):
        return 0
    raiz = os.path.realpath(directory)
    if os.path.dirname(raiz) == raiz:
        logger.error("Limpieza de PDF rechazada: %r es la raiz del sistema de ficheros", directory)
        return 0

    limite = (time.time() if now is None else now) - max_age_seconds
    borrados = 0
    for carpeta, subcarpetas, ficheros in os.walk(raiz, topdown=False, followlinks=False):
        for nombre in ficheros:
            ruta = os.path.join(carpeta, nombre)
            if not nombre.endswith(EXTENSIONES) or os.path.islink(ruta):
                continue
            try:
                if os.path.getmtime(ruta) < limite:
                    os.remove(ruta)
                    borrados += 1
            except FileNotFoundError:
                pass  # otro proceso lo borro entre medias
            except OSError:
                logger.exception("No se pudo borrar %s", ruta)
        if carpeta != raiz:
            try:
                os.rmdir(carpeta)  # solo funciona si esta vacia
            except OSError:
                pass
    return borrados


async def cleanup_loop(
    directory: str, retention_hours: float, interval_minutes: float
) -> None:
    """Bucle de limpieza para el arranque de la aplicacion. Se cancela al apagar."""
    max_age = retention_hours * 3600
    pausa = max(interval_minutes, 0.1) * 60
    logger.info(
        "Limpieza de PDF activa: se borran los de mas de %s h, cada %s min, en %s",
        retention_hours, interval_minutes, directory,
    )
    while True:
        try:
            n = await asyncio.to_thread(delete_old_reports, directory, max_age)
            if n:
                logger.info("Limpieza de PDF: %d borrados", n)
        except Exception:
            # Un fallo puntual no debe parar la limpieza para siempre
            logger.exception("Fallo en la limpieza de PDF")
        await asyncio.sleep(pausa)
