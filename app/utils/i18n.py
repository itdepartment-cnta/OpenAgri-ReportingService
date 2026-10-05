"""Textos de los informes por idioma.

PARCHE CNTA. Los informes originales tienen los textos fijos en ingles. Este
modulo permite elegir el idioma con el parametro `lang`. Por ahora solo los
informes de ganaderia lo usan; los demas siguen en ingles.

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
        "estrus.title": "Livestock Estrus Report",
        "estrus.generated": "Data Generated - {date}",
        "estrus.section_farm": "1. Farm Details",
        "estrus.section_summary": "2. Summary",
        "estrus.section_estrus": "3. Animals in Estrus",
        "estrus.section_uploads": "4. Uploads",
        "estrus.section_detail": "5. Detail per Animal",
        "estrus.period": "Reporting Period",
        "estrus.period_all": "All available data",
        "estrus.farm_name": "Farm Name:",
        "estrus.municipality": "Municipality:",
        "estrus.analyzed": "Animals analyzed",
        "estrus.in_estrus": "In estrus",
        "estrus.not_in_estrus": "Not in estrus",
        "estrus.rate": "Estrus rate",
        "estrus.uploads_count": "Uploads in the period",
        "estrus.chart_title": "Estrus detection per upload",
        "estrus.col_date": "Date",
        "estrus.col_file": "File",
        "estrus.col_animals": "Animals",
        "estrus.col_estrus": "Estrus",
        "estrus.col_no_estrus": "Not in estrus",
        "estrus.col_animal": "Animal",
        "estrus.col_result": "Result",
        "estrus.col_confidence": "Confidence",
        "estrus.result_estrus": "Estrus",
        "estrus.result_no_estrus": "Not in estrus",
        "estrus.none_in_estrus": "No animals in estrus in the period.",
        "estrus.no_uploads": "There are no uploads in the period.",
    },
    "es": {
        "estrus.title": "Informe de detección de celo",
        "estrus.generated": "Generado el {date}",
        "estrus.section_farm": "1. Datos de la granja",
        "estrus.section_summary": "2. Resumen",
        "estrus.section_estrus": "3. Animales en celo",
        "estrus.section_uploads": "4. Subidas",
        "estrus.section_detail": "5. Detalle por animal",
        "estrus.period": "Periodo del informe",
        "estrus.period_all": "Todos los datos disponibles",
        "estrus.farm_name": "Granja:",
        "estrus.municipality": "Municipio:",
        "estrus.analyzed": "Animales analizados",
        "estrus.in_estrus": "En celo",
        "estrus.not_in_estrus": "No en celo",
        "estrus.rate": "Porcentaje en celo",
        "estrus.uploads_count": "Subidas en el periodo",
        "estrus.chart_title": "Detección de celo por subida",
        "estrus.col_date": "Fecha",
        "estrus.col_file": "Fichero",
        "estrus.col_animals": "Animales",
        "estrus.col_estrus": "Celo",
        "estrus.col_no_estrus": "No celo",
        "estrus.col_animal": "Animal",
        "estrus.col_result": "Resultado",
        "estrus.col_confidence": "Confianza",
        "estrus.result_estrus": "Celo",
        "estrus.result_no_estrus": "No celo",
        "estrus.none_in_estrus": "Ningún animal en celo en el periodo.",
        "estrus.no_uploads": "No hay subidas en el periodo.",
    },
}


def t(lang: Optional[str], key: str, **valores) -> str:
    """Texto `key` en `lang`, con caida al ingles y, en ultimo caso, a la clave."""
    texto = TEXTS.get(lang or DEFAULT_LANG, {}).get(key)
    if texto is None:
        texto = TEXTS[DEFAULT_LANG].get(key, key)
    return texto.format(**valores) if valores else texto
