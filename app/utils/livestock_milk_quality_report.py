"""Informe de calidad de leche (recuento de celulas somaticas, SCC).

PARCHE CNTA. Mismo planteamiento que el informe de celo: recibe los datos ya
preparados (ver schemas/livestock.py) y no consulta ninguna base de datos. El
modelo clasifica cada muestra como `low` o `high`; no hay recuento numerico, y
el informe lo dice para que nadie lo lea como tal.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

from schemas.livestock import MilkQualityReportRequest, SccClass
from utils import EX
from utils import report_common as rc
from utils.i18n import t


@dataclass
class UploadStats:
    date: datetime
    filename: str
    total: int
    high: int
    low: int


@dataclass
class Summary:
    total: int = 0
    high: int = 0
    low: int = 0
    uploads: List[UploadStats] = field(default_factory=list)
    # (fecha, muestra) solo de las de recuento alto
    high_rows: List[Tuple[datetime, str]] = field(default_factory=list)
    # (fecha, muestra, resultado) de todas
    detail_rows: List[Tuple[datetime, str, SccClass]] = field(default_factory=list)

    @property
    def high_rate(self) -> Optional[float]:
        """Porcentaje de muestras con recuento alto, o None si no hay muestras."""
        return (self.high / self.total * 100) if self.total else None


def summarize(data: MilkQualityReportRequest) -> Summary:
    s = Summary()
    for up in sorted(data.uploads, key=lambda u: u.upload_date):
        n_high = sum(1 for m in up.samples if m.result == SccClass.high)
        s.uploads.append(
            UploadStats(
                date=up.upload_date,
                filename=up.filename,
                total=len(up.samples),
                high=n_high,
                low=len(up.samples) - n_high,
            )
        )
        s.total += len(up.samples)
        s.high += n_high
        for m in up.samples:
            s.detail_rows.append((up.upload_date, m.sample_id, m.result))
            if m.result == SccClass.high:
                s.high_rows.append((up.upload_date, m.sample_id))
    s.low = s.total - s.high
    return s


def create_milk_quality_pdf(data: MilkQualityReportRequest, lang: str) -> EX:
    summary = summarize(data)
    pdf = rc.nuevo_informe(t(lang, "milk.title"), lang)

    # 1. Datos de la granja
    rc.seccion_granja(pdf, data, lang)

    # 2. Resumen
    rc.seccion(pdf, t(lang, "report.section_summary"))
    rc.tabla(
        pdf,
        [
            t(lang, "milk.analyzed"),
            t(lang, "milk.normal"),
            t(lang, "milk.high"),
            t(lang, "milk.rate"),
            t(lang, "report.uploads_count"),
        ],
        [
            [
                str(summary.total),
                str(summary.low),
                str(summary.high),
                rc.porcentaje(lang, summary.high_rate),
                str(len(summary.uploads)),
            ]
        ],
    )
    pdf.set_font("FreeSerif", "", 8)
    pdf.multi_cell(0, 4, t(lang, "milk.note"), ln=True)
    pdf.set_font("FreeSerif", "", 10)
    pdf.ln(3)
    rc.insertar_grafico(
        pdf,
        rc.grafico_barras_apiladas(
            [u.date.strftime("%d/%m") for u in summary.uploads],
            [u.high for u in summary.uploads],
            [u.low for u in summary.uploads],
            t(lang, "milk.high"),
            t(lang, "milk.normal"),
            t(lang, "milk.chart_title"),
            t(lang, "milk.col_samples"),
        ),
    )

    # 3. Muestras con recuento alto (lo accionable, antes que el detalle)
    rc.seccion(pdf, t(lang, "milk.section_high"))
    if summary.high_rows:
        rc.tabla(
            pdf,
            [t(lang, "milk.col_sample"), t(lang, "report.col_date")],
            [
                [m, rc.fecha(d)]
                for d, m in sorted(summary.high_rows, key=lambda r: (r[0], r[1]), reverse=True)
            ],
        )
    else:
        pdf.cell(0, 8, t(lang, "milk.none_high"), ln=True)
        pdf.ln(2)

    # 4. Subidas
    rc.seccion(pdf, t(lang, "report.section_uploads"))
    if summary.uploads:
        rc.tabla(
            pdf,
            [
                t(lang, "report.col_date"),
                t(lang, "report.col_file"),
                t(lang, "milk.col_samples"),
                t(lang, "milk.col_normal"),
                t(lang, "milk.col_high"),
            ],
            [
                [rc.fecha(u.date), u.filename, str(u.total), str(u.low), str(u.high)]
                for u in summary.uploads
            ],
            anchos=(20, 40, 14, 12, 14),
        )
    else:
        pdf.cell(0, 8, t(lang, "report.no_uploads"), ln=True)
        pdf.ln(2)

    # 5. Detalle por muestra
    if summary.detail_rows:
        rc.seccion(pdf, t(lang, "milk.section_detail"))
        nombre = {
            SccClass.low: t(lang, "milk.result_normal"),
            SccClass.high: t(lang, "milk.result_high"),
        }
        rc.tabla(
            pdf,
            [
                t(lang, "report.col_date"),
                t(lang, "milk.col_sample"),
                t(lang, "milk.col_result"),
            ],
            [[rc.fecha(d), m, nombre[r]] for d, m, r in summary.detail_rows],
        )
    return pdf


def process_milk_quality_data(
    data: MilkQualityReportRequest, lang: str, pdf_file_name: str
) -> None:
    """Genera el PDF en segundo plano (ver report_common.generar_en_segundo_plano)."""
    rc.generar_en_segundo_plano(
        lambda: create_milk_quality_pdf(data, lang),
        pdf_file_name,
        "Milk quality report",
    )
