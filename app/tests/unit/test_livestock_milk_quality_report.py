import os
import tempfile
import time
from datetime import date
from unittest import TestCase
from unittest.mock import patch

from pydantic import ValidationError

# Mismo entorno que test_reports_endpoints.py y test_livestock_estrus_report.py:
# `core.config` crea su objeto UNA vez, con el entorno del primer import.
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
from schemas.livestock import MilkQualityReportRequest  # noqa: E402
from utils.i18n import TEXTS, t  # noqa: E402
from utils.livestock_milk_quality_report import (  # noqa: E402
    create_milk_quality_pdf,
    process_milk_quality_data,
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
                "samples": [
                    {"sample_id": "M001", "result": "high"},
                    {"sample_id": "M002", "result": "low"},
                ],
            },
            {
                "upload_date": "2026-10-01T09:00:00",
                "filename": "a.xlsx",
                "samples": [
                    {"sample_id": "M003", "result": "low"},
                    {"sample_id": "M004", "result": "high"},
                    {"sample_id": "M005", "result": "low"},
                ],
            },
        ],
    }
    base.update(extra)
    return MilkQualityReportRequest.model_validate(base)


class TestTextos(TestCase):
    def test_los_dos_idiomas_tienen_las_mismas_claves(self):
        self.assertEqual(set(TEXTS["en"]), set(TEXTS["es"]))

    def test_aviso_de_que_no_es_un_recuento_numerico(self):
        self.assertIn("numérico", t("es", "milk.note"))
        self.assertIn("not a numeric", t("en", "milk.note"))


class TestEsquema(TestCase):
    def test_periodo_incoherente(self):
        with self.assertRaises(ValidationError):
            _datos(from_date=date(2026, 10, 5), to_date=date(2026, 10, 1))

    def test_resultado_desconocido(self):
        with self.assertRaises(ValidationError):
            MilkQualityReportRequest.model_validate(
                {
                    "farm_name": "G",
                    "uploads": [
                        {
                            "upload_date": "2026-10-01T09:00:00",
                            "samples": [{"sample_id": "M", "result": "Upper"}],
                        }
                    ],
                }
            )

    def test_muestra_sin_identificador(self):
        with self.assertRaises(ValidationError):
            MilkQualityReportRequest.model_validate(
                {
                    "farm_name": "G",
                    "uploads": [
                        {
                            "upload_date": "2026-10-01T09:00:00",
                            "samples": [{"sample_id": "", "result": "low"}],
                        }
                    ],
                }
            )

    def test_granja_sin_nombre(self):
        with self.assertRaises(ValidationError):
            MilkQualityReportRequest.model_validate({"farm_name": ""})


class TestResumen(TestCase):
    def test_cuentas(self):
        s = summarize(_datos())
        self.assertEqual((s.total, s.high, s.low), (5, 2, 3))
        self.assertAlmostEqual(s.high_rate, 40.0)

    def test_subidas_ordenadas_por_fecha(self):
        s = summarize(_datos())
        self.assertEqual([u.filename for u in s.uploads], ["a.xlsx", "b.xlsx"])
        self.assertEqual([(u.total, u.high) for u in s.uploads], [(3, 1), (2, 1)])

    def test_solo_las_muestras_con_recuento_alto(self):
        s = summarize(_datos())
        self.assertEqual({m for _, m in s.high_rows}, {"M001", "M004"})

    def test_sin_datos_no_hay_porcentaje(self):
        s = summarize(_datos(uploads=[]))
        self.assertEqual(s.total, 0)
        self.assertIsNone(s.high_rate)


class TestPdf(TestCase):
    def _pdf(self, datos, lang):
        return bytes(create_milk_quality_pdf(datos, lang).output())

    def test_genera_pdf_en_ambos_idiomas(self):
        for lang in ("en", "es"):
            self.assertTrue(self._pdf(_datos(), lang).startswith(b"%PDF"), lang)

    def test_sin_subidas_tambien_genera(self):
        self.assertTrue(self._pdf(_datos(uploads=[]), "es").startswith(b"%PDF"))

    def test_sin_muestras_de_recuento_alto_tambien_genera(self):
        datos = _datos(
            uploads=[
                {
                    "upload_date": "2026-10-01T09:00:00",
                    "samples": [{"sample_id": "M", "result": "low"}],
                }
            ]
        )
        self.assertTrue(self._pdf(datos, "en").startswith(b"%PDF"))

    def test_muchas_subidas_y_muestras(self):
        datos = _datos(
            uploads=[
                {
                    "upload_date": f"2026-09-{1 + i % 28:02d}T08:00:00",
                    "filename": f"f{i}.xlsx",
                    "samples": [
                        {"sample_id": f"M{i:03d}{j:03d}", "result": "high" if j % 5 == 0 else "low"}
                        for j in range(30)
                    ],
                }
                for i in range(25)
            ]
        )
        self.assertTrue(self._pdf(datos, "es").startswith(b"%PDF"))


class TestSegundoPlano(TestCase):
    def test_escribe_el_pdf_sin_dejar_temporal(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(settings, "PDF_DIRECTORY", d + "/"):
                process_milk_quality_data(_datos(), "es", "livestock/abc")
            self.assertTrue(os.path.exists(f"{d}/livestock/abc.pdf"))
            self.assertFalse(os.path.exists(f"{d}/livestock/abc.pdf.tmp"))

    def test_si_falla_deja_un_marcador_de_error(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(settings, "PDF_DIRECTORY", d + "/"), patch(
                "utils.livestock_milk_quality_report.create_milk_quality_pdf",
                side_effect=RuntimeError("fallo"),
            ):
                process_milk_quality_data(_datos(), "en", "livestock/xyz")
            self.assertTrue(os.path.exists(f"{d}/livestock/xyz.error"))
            self.assertFalse(os.path.exists(f"{d}/livestock/xyz.pdf"))


class TestEndpoint(TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from main import app

        # Sin `with`: no se ejecuta el lifespan (registro en GateKeeper).
        self.client = TestClient(app)
        self.base = "/api/v1/openagri-report/livestock-milk-quality-report/"
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        p = patch.object(settings, "PDF_DIRECTORY", self.dir.name + "/")
        p.start()
        self.addCleanup(p.stop)

    def _esperar(self, uuid):
        for _ in range(40):
            r = self.client.get(f"{self.base}{uuid}/")
            if r.status_code != 202:
                return r
            time.sleep(0.25)
        self.fail("el informe no llego a generarse")

    def test_genera_y_descarga_en_espanol(self):
        r = self.client.post(f"{self.base}?lang=es", json=_datos().model_dump(mode="json"))
        self.assertEqual(r.status_code, 200, r.text)
        descarga = self._esperar(r.json()["uuid"])
        self.assertEqual(descarga.status_code, 200)
        self.assertTrue(descarga.content.startswith(b"%PDF"))

    def test_idioma_no_soportado(self):
        r = self.client.post(f"{self.base}?lang=fr", json=_datos().model_dump(mode="json"))
        self.assertEqual(r.status_code, 422)

    def test_cuerpo_invalido(self):
        self.assertEqual(self.client.post(self.base, json={"farm_name": ""}).status_code, 422)

    def test_identificador_que_no_es_uuid(self):
        self.assertEqual(self.client.get(f"{self.base}no-es-un-uuid/").status_code, 422)

    def test_informe_aun_no_generado_devuelve_202(self):
        r = self.client.get(f"{self.base}00000000-0000-4000-8000-000000000000/")
        self.assertEqual(r.status_code, 202)

    def test_un_informe_de_celo_no_se_sirve_por_la_ruta_de_leche_con_otro_id(self):
        # Los dos comparten carpeta (livestock/<uuid>), pero cada uuid es unico:
        # un id inexistente es 202 en ambas rutas, no un fichero ajeno.
        r = self.client.get(f"{self.base}11111111-1111-4111-8111-111111111111/")
        self.assertEqual(r.status_code, 202)
