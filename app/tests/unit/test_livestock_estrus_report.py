import os
import tempfile
import time
from datetime import date, datetime
from unittest import TestCase
from unittest.mock import patch

from pydantic import ValidationError

# `core.config` crea su objeto de configuracion UNA vez, con el entorno que haya
# en el primer import, y lo comparten todos los tests. Se usa exactamente el
# mismo entorno que test_reports_endpoints.py para que el resultado no dependa
# de que modulo se importe antes.
REQUIRED_ENV_VARS = {
    "REPORTING_GATEKEEPER_USERNAME": "mock_user",
    "REPORTING_GATEKEEPER_PASSWORD": "mock_pass",
    "REPORTING_BACKEND_CORS_ORIGINS": '["*"]',
    "REPORTING_POSTGRES_USER": "mock_pg_user",
    "REPORTING_POSTGRES_PASSWORD": "mock_pg_pass",
    "REPORTING_POSTGRES_DB": "mock_db",
    "REPORTING_POSTGRES_HOST": "mock_host",
    "REPORTING_POSTGRES_PORT": "5432",
    "REPORTING_SERVICE_NAME": "mock_service",
    "REPORTING_SERVICE_PORT": "8000",
    "REPORTING_GATEKEEPER_BASE_URL": "http://mock.gatekeeper",
    "JWT_ACCESS_TOKEN_EXPIRATION_TIME": "3600",
    "JWT_SIGNING_KEY": "mock_jwt_secret",
    "PDF_DIRECTORY": "/",
    "REPORTING_USING_GATEKEEPER": "True",
}
os.environ.update(REQUIRED_ENV_VARS)

from core import settings  # noqa: E402
from schemas.livestock import LivestockEstrusReportRequest  # noqa: E402
from utils.i18n import t  # noqa: E402
from utils.livestock_estrus_report import (  # noqa: E402
    create_livestock_estrus_pdf,
    process_livestock_estrus_data,
    summarize,
)


def _datos(**extra):
    base = {
        "farm_name": "Granja Pamplona",
        "farm_municipality": "Pamplona",
        "uploads": [
            {
                "upload_date": "2026-10-04T10:30:00",
                "filename": "b.xlsx",
                "animals": [
                    {"animal_id": "ES001", "result": "estrus", "confidence": 0.91},
                    {"animal_id": "ES002", "result": "no_estrus", "confidence": 0.8},
                ],
            },
            {
                "upload_date": "2026-10-01T09:00:00",
                "filename": "a.xlsx",
                "animals": [
                    {"animal_id": "ES003", "result": "no_estrus"},
                    {"animal_id": "ES004", "result": "estrus"},
                    {"animal_id": "ES005", "result": "no_estrus"},
                ],
            },
        ],
    }
    base.update(extra)
    return LivestockEstrusReportRequest.model_validate(base)


class TestI18n(TestCase):
    def test_idiomas(self):
        self.assertEqual(t("en", "estrus.in_estrus"), "In estrus")
        self.assertEqual(t("es", "estrus.in_estrus"), "En celo")

    def test_parametros(self):
        self.assertEqual(t("es", "estrus.generated", date="05/10/2026"), "Generado el 05/10/2026")

    def test_idioma_desconocido_o_nulo_cae_al_ingles(self):
        self.assertEqual(t("fr", "estrus.in_estrus"), "In estrus")
        self.assertEqual(t(None, "estrus.in_estrus"), "In estrus")

    def test_clave_inexistente_devuelve_la_clave(self):
        self.assertEqual(t("es", "no.existe"), "no.existe")

    def test_los_dos_idiomas_tienen_las_mismas_claves(self):
        from utils.i18n import TEXTS

        self.assertEqual(set(TEXTS["en"]), set(TEXTS["es"]))


class TestEsquema(TestCase):
    def test_periodo_incoherente(self):
        with self.assertRaises(ValidationError):
            _datos(from_date=date(2026, 10, 5), to_date=date(2026, 10, 1))

    def test_confianza_fuera_de_rango(self):
        with self.assertRaises(ValidationError):
            LivestockEstrusReportRequest.model_validate(
                {
                    "farm_name": "G",
                    "uploads": [
                        {
                            "upload_date": "2026-10-01T09:00:00",
                            "animals": [{"animal_id": "A", "result": "estrus", "confidence": 1.5}],
                        }
                    ],
                }
            )

    def test_resultado_desconocido(self):
        with self.assertRaises(ValidationError):
            LivestockEstrusReportRequest.model_validate(
                {
                    "farm_name": "G",
                    "uploads": [
                        {
                            "upload_date": "2026-10-01T09:00:00",
                            "animals": [{"animal_id": "A", "result": "Celo"}],
                        }
                    ],
                }
            )

    def test_animal_sin_identificador(self):
        with self.assertRaises(ValidationError):
            LivestockEstrusReportRequest.model_validate(
                {
                    "farm_name": "G",
                    "uploads": [
                        {
                            "upload_date": "2026-10-01T09:00:00",
                            "animals": [{"animal_id": "", "result": "estrus"}],
                        }
                    ],
                }
            )


class TestResumen(TestCase):
    def test_cuentas(self):
        s = summarize(_datos())
        self.assertEqual((s.total, s.estrus, s.no_estrus), (5, 2, 3))
        self.assertAlmostEqual(s.estrus_rate, 40.0)

    def test_subidas_ordenadas_por_fecha(self):
        s = summarize(_datos())
        self.assertEqual([u.filename for u in s.uploads], ["a.xlsx", "b.xlsx"])
        self.assertEqual([(u.total, u.estrus) for u in s.uploads], [(3, 1), (2, 1)])

    def test_solo_los_animales_en_celo(self):
        s = summarize(_datos())
        self.assertEqual({a for _, a, _ in s.estrus_rows}, {"ES001", "ES004"})

    def test_sin_datos_no_hay_porcentaje(self):
        s = summarize(_datos(uploads=[]))
        self.assertEqual(s.total, 0)
        self.assertIsNone(s.estrus_rate)


class TestPdf(TestCase):
    def _pdf(self, datos, lang):
        return bytes(create_livestock_estrus_pdf(datos, lang).output())

    def test_genera_pdf_en_ambos_idiomas(self):
        for lang in ("en", "es"):
            self.assertTrue(self._pdf(_datos(), lang).startswith(b"%PDF"), lang)

    def test_sin_subidas_tambien_genera(self):
        self.assertTrue(self._pdf(_datos(uploads=[]), "es").startswith(b"%PDF"))

    def test_sin_animales_en_celo_tambien_genera(self):
        datos = _datos(
            uploads=[
                {
                    "upload_date": "2026-10-01T09:00:00",
                    "animals": [{"animal_id": "A", "result": "no_estrus"}],
                }
            ]
        )
        self.assertTrue(self._pdf(datos, "en").startswith(b"%PDF"))

    def test_con_periodo_y_caracteres_no_ascii(self):
        datos = _datos(
            farm_name="Granja Ñandú — Año 2026",
            from_date=date(2026, 9, 1),
            to_date=date(2026, 10, 5),
        )
        self.assertTrue(self._pdf(datos, "es").startswith(b"%PDF"))

    def test_muchas_subidas_y_animales(self):
        datos = _datos(
            uploads=[
                {
                    "upload_date": datetime(2026, 9, 1 + i % 28, 8, 0).isoformat(),
                    "filename": f"f{i}.xlsx",
                    "animals": [
                        {"animal_id": f"ES{i:03d}{j:03d}", "result": "estrus" if j % 4 == 0 else "no_estrus",
                         "confidence": 0.5 + (j % 5) / 10}
                        for j in range(30)
                    ],
                }
                for i in range(25)
            ]
        )
        self.assertTrue(self._pdf(datos, "es").startswith(b"%PDF"))


class TestGeneracionEnSegundoPlano(TestCase):
    def test_escribe_el_pdf_sin_dejar_temporal(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(settings, "PDF_DIRECTORY", d + "/"):
                process_livestock_estrus_data(_datos(), "es", "livestock/abc")
            self.assertTrue(os.path.exists(f"{d}/livestock/abc.pdf"))
            self.assertFalse(os.path.exists(f"{d}/livestock/abc.pdf.tmp"))

    def test_si_falla_deja_un_marcador_de_error(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(settings, "PDF_DIRECTORY", d + "/"), patch(
                "utils.livestock_estrus_report.create_livestock_estrus_pdf",
                side_effect=RuntimeError("fallo"),
            ):
                process_livestock_estrus_data(_datos(), "en", "livestock/xyz")
            self.assertTrue(os.path.exists(f"{d}/livestock/xyz.error"))
            self.assertFalse(os.path.exists(f"{d}/livestock/xyz.pdf"))


class TestEndpoint(TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from main import app

        # Sin `with`: no se ejecuta el lifespan (registro en GateKeeper).
        self.client = TestClient(app)
        self.base = "/api/v1/openagri-report/livestock-estrus-report/"
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        p = patch.object(settings, "PDF_DIRECTORY", self.dir.name + "/")
        p.start()
        self.addCleanup(p.stop)

    def _esperar_pdf(self, uuid):
        for _ in range(40):
            r = self.client.get(f"{self.base}{uuid}/")
            if r.status_code != 202:
                return r
            time.sleep(0.25)
        self.fail("el informe no llego a generarse")

    def test_genera_y_descarga_en_espanol(self):
        cuerpo = _datos().model_dump(mode="json")
        r = self.client.post(f"{self.base}?lang=es", json=cuerpo)
        self.assertEqual(r.status_code, 200, r.text)
        descarga = self._esperar_pdf(r.json()["uuid"])
        self.assertEqual(descarga.status_code, 200)
        self.assertTrue(descarga.content.startswith(b"%PDF"))

    def test_idioma_no_soportado(self):
        r = self.client.post(f"{self.base}?lang=fr", json=_datos().model_dump(mode="json"))
        self.assertEqual(r.status_code, 422)

    def test_cuerpo_invalido(self):
        r = self.client.post(self.base, json={"farm_name": ""})
        self.assertEqual(r.status_code, 422)

    def test_identificador_que_no_es_uuid(self):
        # Evita recorrer directorios con el id de la URL
        r = self.client.get(f"{self.base}..%2F..%2Fetc%2Fpasswd/")
        self.assertIn(r.status_code, (404, 422))
        r = self.client.get(f"{self.base}no-es-un-uuid/")
        self.assertEqual(r.status_code, 422)

    def test_informe_aun_no_generado_devuelve_202(self):
        r = self.client.get(f"{self.base}00000000-0000-4000-8000-000000000000/")
        self.assertEqual(r.status_code, 202)
