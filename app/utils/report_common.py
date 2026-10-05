"""Piezas comunes de los informes de ganaderia (celo, calidad de leche).

PARCHE CNTA. Cabecera, datos de la granja, tablas, grafico de barras y la
escritura del PDF en segundo plano son iguales en todos los informes de
ganaderia; viven aqui para no repetirlos.
"""

import io
import logging
import os
from datetime import date, datetime
from typing import Callable, List, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from fpdf.fonts import FontFace  # noqa: E402

from core import settings  # noqa: E402
from utils import EX, add_fonts  # noqa: E402
from utils.i18n import t  # noqa: E402

logger = logging.getLogger(__name__)

# Barras del grafico: mas de esto no se lee bien en una pagina
MAX_BARRAS_GRAFICO = 15
ALTO_GRAFICO_MM = 170 * 3 / 7  # figsize (7, 3) a 170 mm de ancho


def numero(lang: str, valor: float, decimales: int = 1) -> str:
    texto = f"{valor:.{decimales}f}"
    return texto.replace(".", ",") if lang == "es" else texto


def fecha(d: datetime) -> str:
    return d.strftime("%d/%m/%Y")


def porcentaje(lang: str, valor: Optional[float]) -> str:
    return "—" if valor is None else f"{numero(lang, valor)} %"


def periodo(data, lang: str) -> str:
    """Texto del periodo del informe. `data` tiene from_date y to_date."""
    if not (data.from_date or data.to_date):
        return t(lang, "report.period_all")
    desde = data.from_date.strftime("%d/%m/%Y") if data.from_date else ""
    hasta = data.to_date.strftime("%d/%m/%Y") if data.to_date else ""
    return f"{desde} - {hasta}"


def nuevo_informe(titulo: str, lang: str) -> EX:
    """PDF con la cabecera: logo, titulo, fecha de generacion y una linea."""
    pdf = EX()
    add_fonts(pdf)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    EX.ln(pdf)

    pdf.set_font("FreeSerif", "B", 14)
    pdf.cell(0, 10, titulo, ln=True, align="C")
    pdf.set_font("FreeSerif", "", 9)
    pdf.cell(
        0, 7, t(lang, "report.generated", date=fecha(datetime.now())), ln=True, align="C"
    )
    pdf.ln(3)
    y = pdf.get_y()
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.ln(5)
    return pdf


def seccion(pdf: EX, titulo: str) -> None:
    pdf.set_font("FreeSerif", "B", 14)
    pdf.cell(0, 9, titulo, ln=True)
    pdf.set_font("FreeSerif", "", 10)


def seccion_granja(pdf: EX, data, lang: str) -> None:
    """Seccion 1: periodo, nombre y municipio. `data` es la peticion del informe."""
    seccion(pdf, t(lang, "report.section_farm"))
    for etiqueta, valor in (
        (t(lang, "report.period"), periodo(data, lang)),
        (t(lang, "report.farm_name"), data.farm_name),
        (t(lang, "report.municipality"), data.farm_municipality),
    ):
        pdf.set_font("FreeSerif", "B", 10)
        pdf.cell(50, 7, etiqueta)
        pdf.set_font("FreeSerif", "", 10)
        pdf.multi_cell(0, 7, valor, ln=True)
    pdf.ln(4)


def tabla(pdf: EX, cabeceras: List[str], filas: List[List[str]], anchos=None) -> None:
    pdf.set_font("FreeSerif", "", 9)
    with pdf.table(
        headings_style=FontFace(emphasis="BOLD", fill_color=(225, 225, 225)),
        text_align="CENTER",
        padding=0.6,
        col_widths=anchos,
    ) as t_:
        fila = t_.row()
        for c in cabeceras:
            fila.cell(c)
        for datos in filas:
            fila = t_.row()
            for celda in datos:
                fila.cell(celda)
    pdf.set_font("FreeSerif", "", 10)
    pdf.ln(4)


def grafico_barras_apiladas(
    etiquetas: List[str],
    positivos: List[int],
    negativos: List[int],
    etiqueta_positivos: str,
    etiqueta_negativos: str,
    titulo: str,
    eje_y: str,
) -> Optional[io.BytesIO]:
    """Barras apiladas por subida: positivos (rojo) sobre negativos (verde).

    Se limita a las ultimas MAX_BARRAS_GRAFICO. Devuelve None si no hay datos.
    """
    if not etiquetas:
        return None
    etiquetas = etiquetas[-MAX_BARRAS_GRAFICO:]
    positivos = positivos[-MAX_BARRAS_GRAFICO:]
    negativos = negativos[-MAX_BARRAS_GRAFICO:]

    fig, ax = plt.subplots(figsize=(7, 3))
    try:
        ax.bar(etiquetas, positivos, color="#d9534f", label=etiqueta_positivos)
        ax.bar(etiquetas, negativos, bottom=positivos, color="#5cb85c", label=etiqueta_negativos)
        ax.set_title(titulo, fontsize=10)
        ax.set_ylabel(eje_y, fontsize=8)
        ax.tick_params(axis="x", labelsize=7, rotation=45)
        ax.tick_params(axis="y", labelsize=7)
        ax.yaxis.get_major_locator().set_params(integer=True)
        ax.legend(fontsize=7)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150)
        buf.seek(0)
        return buf
    finally:
        plt.close(fig)


def insertar_grafico(pdf: EX, grafico: Optional[io.BytesIO]) -> None:
    if grafico is None:
        return
    if pdf.get_y() + ALTO_GRAFICO_MM > pdf.h - 25:
        pdf.add_page()
    pdf.image(grafico, x=(pdf.w - 170) / 2, w=170)
    pdf.ln(4)


def generar_en_segundo_plano(
    construir: Callable[[], EX], pdf_file_name: str, nombre_informe: str
) -> None:
    """Construye el PDF y lo escribe en PDF_DIRECTORY/<pdf_file_name>.pdf.

    Se escribe a un fichero temporal y se renombra al terminar: quien consulta
    el informe nunca ve un PDF a medias. Si falla, se deja un `.error` para que
    el cliente pueda dejar de esperar (los demas informes devuelven 202
    indefinidamente cuando fallan).
    """
    destino = f"{settings.PDF_DIRECTORY}{pdf_file_name}.pdf"
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    try:
        pdf = construir()
        pdf.output(f"{destino}.tmp")
        os.replace(f"{destino}.tmp", destino)
    except Exception:
        logger.exception("%s generation failed", nombre_informe)
        with open(f"{destino[:-4]}.error", "w", encoding="utf-8") as f:
            f.write("generation failed")
