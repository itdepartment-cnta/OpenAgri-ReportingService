"""Informe de deteccion de celo en ganaderia.

PARCHE CNTA. A diferencia del resto de informes, no consulta Farm Calendar ni
ninguna base de datos: recibe los datos ya preparados (ver
schemas/livestock.py). Asi sirve para cualquier origen de datos y no depende de
GateKeeper. El periodo (`from_date`/`to_date`) es informativo: se imprime en la
cabecera, pero quien llama es quien filtra los datos.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

from schemas.livestock import EstrusResult, LivestockEstrusReportRequest
from utils import EX
from utils import report_common as rc
from utils.i18n import t


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


def _confianza(lang: str, c: Optional[float]) -> str:
    return "—" if c is None else f"{rc.numero(lang, c * 100, 0)} %"


def create_livestock_estrus_pdf(data: LivestockEstrusReportRequest, lang: str) -> EX:
    summary = summarize(data)
    pdf = rc.nuevo_informe(t(lang, "estrus.title"), lang)

    # 1. Datos de la granja
    rc.seccion_granja(pdf, data, lang)

    # 2. Resumen
    rc.seccion(pdf, t(lang, "report.section_summary"))
    rc.tabla(
        pdf,
        [
            t(lang, "estrus.analyzed"),
            t(lang, "estrus.in_estrus"),
            t(lang, "estrus.not_in_estrus"),
            t(lang, "estrus.rate"),
            t(lang, "report.uploads_count"),
        ],
        [
            [
                str(summary.total),
                str(summary.estrus),
                str(summary.no_estrus),
                rc.porcentaje(lang, summary.estrus_rate),
                str(len(summary.uploads)),
            ]
        ],
    )
    rc.insertar_grafico(
        pdf,
        rc.grafico_barras_apiladas(
            [u.date.strftime("%d/%m") for u in summary.uploads],
            [u.estrus for u in summary.uploads],
            [u.no_estrus for u in summary.uploads],
            t(lang, "estrus.in_estrus"),
            t(lang, "estrus.not_in_estrus"),
            t(lang, "estrus.chart_title"),
            t(lang, "estrus.col_animals"),
        ),
    )

    # 3. Animales en celo (lo que consulta el ganadero, antes que el detalle)
    rc.seccion(pdf, t(lang, "estrus.section_estrus"))
    if summary.estrus_rows:
        rc.tabla(
            pdf,
            [
                t(lang, "estrus.col_animal"),
                t(lang, "report.col_date"),
                t(lang, "estrus.col_confidence"),
            ],
            [
                [a, rc.fecha(d), _confianza(lang, c)]
                for d, a, c in sorted(
                    summary.estrus_rows, key=lambda r: (r[0], r[1]), reverse=True
                )
            ],
        )
    else:
        pdf.cell(0, 8, t(lang, "estrus.none_in_estrus"), ln=True)
        pdf.ln(2)

    # 4. Subidas
    rc.seccion(pdf, t(lang, "report.section_uploads"))
    if summary.uploads:
        rc.tabla(
            pdf,
            [
                t(lang, "report.col_date"),
                t(lang, "report.col_file"),
                t(lang, "estrus.col_animals"),
                t(lang, "estrus.col_estrus"),
                t(lang, "estrus.col_no_estrus"),
            ],
            [
                [rc.fecha(u.date), u.filename, str(u.total), str(u.estrus), str(u.no_estrus)]
                for u in summary.uploads
            ],
            anchos=(20, 40, 14, 12, 14),
        )
    else:
        pdf.cell(0, 8, t(lang, "report.no_uploads"), ln=True)
        pdf.ln(2)

    # 5. Detalle por animal
    if summary.detail_rows:
        rc.seccion(pdf, t(lang, "estrus.section_detail"))
        nombre = {
            EstrusResult.estrus: t(lang, "estrus.result_estrus"),
            EstrusResult.no_estrus: t(lang, "estrus.result_no_estrus"),
        }
        rc.tabla(
            pdf,
            [
                t(lang, "report.col_date"),
                t(lang, "estrus.col_animal"),
                t(lang, "estrus.col_result"),
                t(lang, "estrus.col_confidence"),
            ],
            [
                [rc.fecha(d), a, nombre[r], _confianza(lang, c)]
                for d, a, r, c in summary.detail_rows
            ],
        )
    return pdf


def process_livestock_estrus_data(
    data: LivestockEstrusReportRequest, lang: str, pdf_file_name: str
) -> None:
    """Genera el PDF en segundo plano (ver report_common.generar_en_segundo_plano)."""
    rc.generar_en_segundo_plano(
        lambda: create_livestock_estrus_pdf(data, lang),
        pdf_file_name,
        "Livestock estrus report",
    )
