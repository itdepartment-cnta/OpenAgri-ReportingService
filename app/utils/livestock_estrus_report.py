"""Informe de deteccion de celo en ganaderia.

PARCHE CNTA. A diferencia del resto de informes, no consulta Farm Calendar ni
ninguna base de datos: recibe los datos ya preparados (ver
schemas/livestock.py). Asi sirve para cualquier origen de datos y no depende de
GateKeeper. El periodo (`from_date`/`to_date`) es informativo: se imprime en la
cabecera, pero quien llama es quien filtra los datos.
"""

import io
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from fpdf.fonts import FontFace  # noqa: E402

from core import settings  # noqa: E402
from schemas.livestock import EstrusResult, LivestockEstrusReportRequest  # noqa: E402
from utils import EX, add_fonts  # noqa: E402
from utils.i18n import t  # noqa: E402

logger = logging.getLogger(__name__)

# Barras del grafico: mas de esto no se lee bien en una pagina
MAX_BARRAS_GRAFICO = 15


@dataclass
class UploadStats:
    date: datetime
    filename: str
    total: int
    estrus: int
    no_estrus: int


@dataclass
class Summary:
    total: int = 0
    estrus: int = 0
    no_estrus: int = 0
    uploads: List[UploadStats] = field(default_factory=list)
    # (fecha, animal, confianza) solo de los animales en celo
    estrus_rows: List[Tuple[datetime, str, Optional[float]]] = field(default_factory=list)
    # (fecha, animal, resultado, confianza) de todos
    detail_rows: List[Tuple[datetime, str, EstrusResult, Optional[float]]] = field(
        default_factory=list
    )

    @property
    def estrus_rate(self) -> Optional[float]:
        """Porcentaje de animales en celo, o None si no hay animales."""
        return (self.estrus / self.total * 100) if self.total else None


def summarize(data: LivestockEstrusReportRequest) -> Summary:
    s = Summary()
    for up in sorted(data.uploads, key=lambda u: u.upload_date):
        n_estrus = sum(1 for a in up.animals if a.result == EstrusResult.estrus)
        s.uploads.append(
            UploadStats(
                date=up.upload_date,
                filename=up.filename,
                total=len(up.animals),
                estrus=n_estrus,
                no_estrus=len(up.animals) - n_estrus,
            )
        )
        s.total += len(up.animals)
        s.estrus += n_estrus
        for a in up.animals:
            s.detail_rows.append((up.upload_date, a.animal_id, a.result, a.confidence))
            if a.result == EstrusResult.estrus:
                s.estrus_rows.append((up.upload_date, a.animal_id, a.confidence))
    s.no_estrus = s.total - s.estrus
    return s


def _numero(lang: str, valor: float, decimales: int = 1) -> str:
    texto = f"{valor:.{decimales}f}"
    return texto.replace(".", ",") if lang == "es" else texto


def _fecha(d: datetime) -> str:
    return d.strftime("%d/%m/%Y")


def _confianza(lang: str, c: Optional[float]) -> str:
    return "—" if c is None else f"{_numero(lang, c * 100, 0)} %"


def _grafico(summary: Summary, lang: str) -> Optional[io.BytesIO]:
    if not summary.uploads:
        return None
    ultimas = summary.uploads[-MAX_BARRAS_GRAFICO:]
    etiquetas = [u.date.strftime("%d/%m") for u in ultimas]

    fig, ax = plt.subplots(figsize=(7, 3))
    try:
        ax.bar(
            etiquetas,
            [u.estrus for u in ultimas],
            color="#d9534f",
            label=t(lang, "estrus.in_estrus"),
        )
        ax.bar(
            etiquetas,
            [u.no_estrus for u in ultimas],
            bottom=[u.estrus for u in ultimas],
            color="#5cb85c",
            label=t(lang, "estrus.not_in_estrus"),
        )
        ax.set_title(t(lang, "estrus.chart_title"), fontsize=10)
        ax.set_ylabel(t(lang, "estrus.col_animals"), fontsize=8)
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


def _seccion(pdf: EX, titulo: str) -> None:
    pdf.set_font("FreeSerif", "B", 14)
    pdf.cell(0, 9, titulo, ln=True)
    pdf.set_font("FreeSerif", "", 10)


def _tabla(pdf: EX, cabeceras: List[str], filas: List[List[str]], anchos=None) -> None:
    pdf.set_font("FreeSerif", "", 9)
    with pdf.table(
        headings_style=FontFace(emphasis="BOLD", fill_color=(225, 225, 225)),
        text_align="CENTER",
        padding=0.6,
        col_widths=anchos,
    ) as tabla:
        fila = tabla.row()
        for c in cabeceras:
            fila.cell(c)
        for datos in filas:
            fila = tabla.row()
            for celda in datos:
                fila.cell(celda)
    pdf.set_font("FreeSerif", "", 10)
    pdf.ln(4)


def _periodo(data: LivestockEstrusReportRequest, lang: str) -> str:
    if not (data.from_date or data.to_date):
        return t(lang, "estrus.period_all")
    desde = data.from_date.strftime("%d/%m/%Y") if data.from_date else ""
    hasta = data.to_date.strftime("%d/%m/%Y") if data.to_date else ""
    return f"{desde} - {hasta}"


def create_livestock_estrus_pdf(data: LivestockEstrusReportRequest, lang: str) -> EX:
    summary = summarize(data)

    pdf = EX()
    add_fonts(pdf)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    EX.ln(pdf)

    pdf.set_font("FreeSerif", "B", 14)
    pdf.cell(0, 10, t(lang, "estrus.title"), ln=True, align="C")
    pdf.set_font("FreeSerif", "", 9)
    pdf.cell(
        0, 7, t(lang, "estrus.generated", date=_fecha(datetime.now())), ln=True, align="C"
    )
    pdf.ln(3)
    y = pdf.get_y()
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.ln(5)

    # 1. Datos de la granja
    _seccion(pdf, t(lang, "estrus.section_farm"))
    for etiqueta, valor in (
        (t(lang, "estrus.period"), _periodo(data, lang)),
        (t(lang, "estrus.farm_name"), data.farm_name),
        (t(lang, "estrus.municipality"), data.farm_municipality),
    ):
        pdf.set_font("FreeSerif", "B", 10)
        pdf.cell(50, 7, etiqueta)
        pdf.set_font("FreeSerif", "", 10)
        pdf.multi_cell(0, 7, valor, ln=True)
    pdf.ln(4)

    # 2. Resumen
    _seccion(pdf, t(lang, "estrus.section_summary"))
    tasa = "—" if summary.estrus_rate is None else f"{_numero(lang, summary.estrus_rate)} %"
    _tabla(
        pdf,
        [
            t(lang, "estrus.analyzed"),
            t(lang, "estrus.in_estrus"),
            t(lang, "estrus.not_in_estrus"),
            t(lang, "estrus.rate"),
            t(lang, "estrus.uploads_count"),
        ],
        [
            [
                str(summary.total),
                str(summary.estrus),
                str(summary.no_estrus),
                tasa,
                str(len(summary.uploads)),
            ]
        ],
    )

    grafico = _grafico(summary, lang)
    if grafico is not None:
        alto = 170 * 3 / 7
        if pdf.get_y() + alto > pdf.h - 25:
            pdf.add_page()
        pdf.image(grafico, x=(pdf.w - 170) / 2, w=170)
        pdf.ln(4)

    # 3. Animales en celo (lo que consulta el ganadero, antes que el detalle)
    _seccion(pdf, t(lang, "estrus.section_estrus"))
    if summary.estrus_rows:
        _tabla(
            pdf,
            [
                t(lang, "estrus.col_animal"),
                t(lang, "estrus.col_date"),
                t(lang, "estrus.col_confidence"),
            ],
            [
                [a, _fecha(d), _confianza(lang, c)]
                for d, a, c in sorted(
                    summary.estrus_rows, key=lambda r: (r[0], r[1]), reverse=True
                )
            ],
        )
    else:
        pdf.cell(0, 8, t(lang, "estrus.none_in_estrus"), ln=True)
        pdf.ln(2)

    # 4. Subidas
    _seccion(pdf, t(lang, "estrus.section_uploads"))
    if summary.uploads:
        _tabla(
            pdf,
            [
                t(lang, "estrus.col_date"),
                t(lang, "estrus.col_file"),
                t(lang, "estrus.col_animals"),
                t(lang, "estrus.col_estrus"),
                t(lang, "estrus.col_no_estrus"),
            ],
            [
                [_fecha(u.date), u.filename, str(u.total), str(u.estrus), str(u.no_estrus)]
                for u in summary.uploads
            ],
            anchos=(20, 40, 14, 12, 14),
        )
    else:
        pdf.cell(0, 8, t(lang, "estrus.no_uploads"), ln=True)
        pdf.ln(2)

    # 5. Detalle por animal
    if summary.detail_rows:
        _seccion(pdf, t(lang, "estrus.section_detail"))
        nombre = {
            EstrusResult.estrus: t(lang, "estrus.result_estrus"),
            EstrusResult.no_estrus: t(lang, "estrus.result_no_estrus"),
        }
        _tabla(
            pdf,
            [
                t(lang, "estrus.col_date"),
                t(lang, "estrus.col_animal"),
                t(lang, "estrus.col_result"),
                t(lang, "estrus.col_confidence"),
            ],
            [
                [_fecha(d), a, nombre[r], _confianza(lang, c)]
                for d, a, r, c in summary.detail_rows
            ],
        )
    return pdf


def process_livestock_estrus_data(
    data: LivestockEstrusReportRequest, lang: str, pdf_file_name: str
) -> None:
    """Genera el PDF en segundo plano.

    Se escribe a un fichero temporal y se renombra al terminar: quien consulta
    el informe nunca ve un PDF a medias. Si falla, se deja un `.error` para que
    el cliente pueda dejar de esperar (los demas informes devuelven 202
    indefinidamente cuando fallan).
    """
    destino = f"{settings.PDF_DIRECTORY}{pdf_file_name}.pdf"
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    try:
        pdf = create_livestock_estrus_pdf(data, lang)
        pdf.output(f"{destino}.tmp")
        os.replace(f"{destino}.tmp", destino)
    except Exception:
        logger.exception("Livestock estrus report generation failed")
        with open(f"{destino[:-4]}.error", "w", encoding="utf-8") as f:
            f.write("generation failed")
