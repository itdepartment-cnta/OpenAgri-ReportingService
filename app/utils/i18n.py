"""Textos de los informes por idioma.

PARCHE CNTA. Los informes originales tienen los textos fijos en ingles. Este
modulo permite elegir el idioma con el parametro `lang`. Por ahora solo los
informes de ganaderia lo usan; los demas siguen en ingles.

Las claves `report.*` son comunes a los informes de ganaderia; `estrus.*` y
`milk.*` son propias de cada uno.

Para anadir un idioma: una entrada nueva en TEXTS con las mismas claves y su
codigo en Lang. Una clave que falte cae al ingles, y si tampoco esta, se
devuelve la propia clave, para que un texto sin traducir se vea en el PDF en
lugar de romper la generacion.
"""

from typing import Literal, Optional

Lang = Literal["en", "es"]
DEFAULT_LANG: Lang = "en"

TEXTS = {
    "en": {
        # ── comunes ──────────────────────────────────────────────
        "report.generated": "Data Generated - {date}",
        "report.section_farm": "1. Farm Details",
        "report.section_summary": "2. Summary",
        "report.section_uploads": "4. Uploads",
        "report.period": "Reporting Period",
        "report.period_all": "All available data",
        "report.farm_name": "Farm Name:",
        "report.municipality": "Municipality:",
        "report.uploads_count": "Uploads in the period",
        "report.col_date": "Date",
        "report.col_file": "File",
        "report.no_uploads": "There are no uploads in the period.",
        # ── celo ─────────────────────────────────────────────────
        "estrus.title": "Livestock Estrus Report",
        "estrus.section_estrus": "3. Animals in Estrus",
        "estrus.section_detail": "5. Detail per Animal",
        "estrus.analyzed": "Animals analyzed",
        "estrus.in_estrus": "In estrus",
        "estrus.not_in_estrus": "Not in estrus",
        "estrus.rate": "Estrus rate",
        "estrus.chart_title": "Estrus detection per upload",
        "estrus.col_animals": "Animals",
        "estrus.col_estrus": "Estrus",
        "estrus.col_no_estrus": "Not in estrus",
        "estrus.col_animal": "Animal",
        "estrus.col_result": "Result",
        "estrus.col_confidence": "Confidence",
        "estrus.result_estrus": "Estrus",
        "estrus.result_no_estrus": "Not in estrus",
        "estrus.none_in_estrus": "No animals in estrus in the period.",
        # ── calidad de leche ─────────────────────────────────────
        "milk.title": "Milk Quality (SCC) Report",
        "milk.section_high": "3. Samples with High SCC",
        "milk.section_detail": "5. Detail per Sample",
        "milk.analyzed": "Samples analyzed",
        "milk.normal": "Normal SCC",
        "milk.high": "High SCC",
        "milk.rate": "High SCC rate",
        "milk.chart_title": "Milk quality per upload",
        "milk.col_samples": "Samples",
        "milk.col_normal": "Normal",
        "milk.col_high": "High",
        "milk.col_sample": "Sample",
        "milk.col_result": "Result",
        "milk.result_normal": "Normal SCC",
        "milk.result_high": "High SCC",
        "milk.none_high": "No samples with high SCC in the period.",
        "milk.note": (
            "Classification by the model from each sample's spectrum "
            "(somatic cell count, SCC). It is not a numeric count."
        ),
    },
    "es": {
        # ── comunes ──────────────────────────────────────────────
        "report.generated": "Generado el {date}",
        "report.section_farm": "1. Datos de la granja",
        "report.section_summary": "2. Resumen",
        "report.section_uploads": "4. Subidas",
        "report.period": "Periodo del informe",
        "report.period_all": "Todos los datos disponibles",
        "report.farm_name": "Granja:",
        "report.municipality": "Municipio:",
        "report.uploads_count": "Subidas en el periodo",
        "report.col_date": "Fecha",
        "report.col_file": "Fichero",
        "report.no_uploads": "No hay subidas en el periodo.",
        # ── celo ─────────────────────────────────────────────────
        "estrus.title": "Informe de detección de celo",
        "estrus.section_estrus": "3. Animales en celo",
        "estrus.section_detail": "5. Detalle por animal",
        "estrus.analyzed": "Animales analizados",
        "estrus.in_estrus": "En celo",
        "estrus.not_in_estrus": "No en celo",
        "estrus.rate": "Porcentaje en celo",
        "estrus.chart_title": "Detección de celo por subida",
        "estrus.col_animals": "Animales",
        "estrus.col_estrus": "Celo",
        "estrus.col_no_estrus": "No celo",
        "estrus.col_animal": "Animal",
        "estrus.col_result": "Resultado",
        "estrus.col_confidence": "Confianza",
        "estrus.result_estrus": "Celo",
        "estrus.result_no_estrus": "No celo",
        "estrus.none_in_estrus": "Ningún animal en celo en el periodo.",
        # ── calidad de leche ─────────────────────────────────────
        "milk.title": "Informe de calidad de leche (SCC)",
        "milk.section_high": "3. Muestras con calidad mala",
        "milk.section_detail": "5. Detalle por muestra",
        "milk.analyzed": "Muestras analizadas",
        "milk.normal": "Calidad buena",
        "milk.high": "Calidad mala",
        "milk.rate": "Porcentaje con calidad mala",
        "milk.chart_title": "Calidad de leche por subida",
        "milk.col_samples": "Muestras",
        "milk.col_normal": "Buena",
        "milk.col_high": "Mala",
        "milk.col_sample": "Muestra",
        "milk.col_result": "Resultado",
        "milk.result_normal": "Calidad buena",
        "milk.result_high": "Calidad mala",
        "milk.none_high": "Ninguna muestra con calidad mala en el periodo.",
        "milk.note": (
            "Clasificación del modelo a partir del espectro de cada muestra "
            "(recuento de células somáticas, SCC). No es un recuento numérico."
        ),
    },
}


def t(lang: Optional[str], key: str, **valores) -> str:
    """Texto `key` en `lang`, con caida al ingles y, en ultimo caso, a la clave."""
    texto = TEXTS.get(lang or DEFAULT_LANG, {}).get(key)
    if texto is None:
        texto = TEXTS[DEFAULT_LANG].get(key, key)
    return texto.format(**valores) if valores else texto
