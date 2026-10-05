import asyncio
import os
import tempfile
import time
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

from utils.pdf_cleanup import cleanup_loop, delete_old_reports

HORA = 3600


def _crear(ruta, antiguedad_s=0, contenido=b"x"):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "wb") as f:
        f.write(contenido)
    t = time.time() - antiguedad_s
    os.utime(ruta, (t, t))


class TestDeleteOldReports(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = self.tmp.name

    def _existe(self, *partes):
        return os.path.exists(os.path.join(self.d, *partes))

    def test_borra_los_viejos_y_conserva_los_recientes(self):
        _crear(f"{self.d}/livestock/viejo.pdf", 3 * HORA)
        _crear(f"{self.d}/livestock/reciente.pdf", 10)
        self.assertEqual(delete_old_reports(self.d, HORA), 1)
        self.assertFalse(self._existe("livestock", "viejo.pdf"))
        self.assertTrue(self._existe("livestock", "reciente.pdf"))

    def test_borra_tambien_temporales_y_marcadores_de_error(self):
        _crear(f"{self.d}/livestock/a.pdf.tmp", 3 * HORA)
        _crear(f"{self.d}/livestock/b.error", 3 * HORA)
        self.assertEqual(delete_old_reports(self.d, HORA), 2)

    def test_no_toca_ficheros_de_otro_tipo(self):
        _crear(f"{self.d}/notas.txt", 100 * HORA)
        _crear(f"{self.d}/livestock/.gitkeep", 100 * HORA)
        _crear(f"{self.d}/datos.json", 100 * HORA)
        self.assertEqual(delete_old_reports(self.d, HORA), 0)
        self.assertTrue(self._existe("notas.txt"))
        self.assertTrue(self._existe("livestock", ".gitkeep"))
        self.assertTrue(self._existe("datos.json"))

    def test_recursivo_en_las_carpetas_por_usuario_y_tipo(self):
        _crear(f"{self.d}/123/uuid1.pdf", 5 * HORA)
        _crear(f"{self.d}/standalone/uuid2.pdf", 5 * HORA)
        _crear(f"{self.d}/livestock/uuid3.pdf", 5 * HORA)
        self.assertEqual(delete_old_reports(self.d, HORA), 3)

    def test_quita_las_carpetas_que_quedan_vacias_pero_no_la_raiz(self):
        _crear(f"{self.d}/livestock/a.pdf", 5 * HORA)
        _crear(f"{self.d}/otra/b.pdf", 10)  # esta carpeta no queda vacia
        delete_old_reports(self.d, HORA)
        self.assertFalse(self._existe("livestock"))
        self.assertTrue(self._existe("otra"))
        self.assertTrue(os.path.isdir(self.d))

    def test_no_borra_una_carpeta_con_ficheros_ajenos(self):
        _crear(f"{self.d}/livestock/a.pdf", 5 * HORA)
        _crear(f"{self.d}/livestock/ajeno.txt", 5 * HORA)
        delete_old_reports(self.d, HORA)
        self.assertFalse(self._existe("livestock", "a.pdf"))
        self.assertTrue(self._existe("livestock", "ajeno.txt"))

    def test_el_limite_es_estricto(self):
        ahora = time.time()
        _crear(f"{self.d}/justo.pdf", 0)
        os.utime(f"{self.d}/justo.pdf", (ahora - HORA, ahora - HORA))
        # exactamente en el limite: no es MAS viejo que el limite
        self.assertEqual(delete_old_reports(self.d, HORA, now=ahora), 0)
        self.assertEqual(delete_old_reports(self.d, HORA, now=ahora + 1), 1)

    def test_no_sigue_enlaces_simbolicos(self):
        with tempfile.TemporaryDirectory() as fuera:
            _crear(f"{fuera}/importante.pdf", 100 * HORA)
            try:
                os.symlink(fuera, os.path.join(self.d, "enlace"))
                os.symlink(f"{fuera}/importante.pdf", os.path.join(self.d, "directo.pdf"))
            except (OSError, NotImplementedError):
                self.skipTest("el sistema no permite crear enlaces simbolicos")
            delete_old_reports(self.d, HORA)
            self.assertTrue(os.path.exists(f"{fuera}/importante.pdf"))

    def test_se_niega_a_trabajar_sobre_la_raiz_del_sistema(self):
        raiz = os.path.abspath(os.sep)
        with patch("utils.pdf_cleanup.os.walk") as caminar:
            self.assertEqual(delete_old_reports(raiz, 0), 0)
            caminar.assert_not_called()

    def test_directorio_inexistente_o_vacio(self):
        self.assertEqual(delete_old_reports(f"{self.d}/no-existe", HORA), 0)
        self.assertEqual(delete_old_reports("", HORA), 0)

    def test_un_fallo_al_borrar_uno_no_impide_borrar_los_demas(self):
        _crear(f"{self.d}/a.pdf", 5 * HORA)
        _crear(f"{self.d}/b.pdf", 5 * HORA)
        real = os.remove
        llamadas = []

        def remove_con_fallo(ruta):
            llamadas.append(ruta)
            if ruta.endswith("a.pdf"):
                raise PermissionError("sin permiso")
            real(ruta)

        with patch("utils.pdf_cleanup.os.remove", side_effect=remove_con_fallo):
            self.assertEqual(delete_old_reports(self.d, HORA), 1)
        self.assertEqual(len(llamadas), 2)


class TestCleanupLoop(IsolatedAsyncioTestCase):
    async def test_borra_en_la_primera_pasada_y_se_cancela_limpiamente(self):
        with tempfile.TemporaryDirectory() as d:
            _crear(f"{d}/livestock/viejo.pdf", 5 * HORA)
            tarea = asyncio.create_task(cleanup_loop(d, 1, 60))
            for _ in range(50):
                if not os.path.exists(f"{d}/livestock/viejo.pdf"):
                    break
                await asyncio.sleep(0.05)
            self.assertFalse(os.path.exists(f"{d}/livestock/viejo.pdf"))
            tarea.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await tarea

    async def test_un_error_en_una_pasada_no_para_el_bucle(self):
        llamadas = []

        def falla_la_primera(*args, **kwargs):
            llamadas.append(1)
            if len(llamadas) == 1:
                raise RuntimeError("fallo puntual")
            return 0

        with patch("utils.pdf_cleanup.delete_old_reports", side_effect=falla_la_primera):
            # intervalo minimo (0.1 min = 6 s) -> se acorta parcheando sleep
            real_sleep = asyncio.sleep

            async def sleep_corto(_):
                await real_sleep(0.01)

            with patch("utils.pdf_cleanup.asyncio.sleep", sleep_corto):
                tarea = asyncio.create_task(cleanup_loop("/tmp", 1, 1))
                for _ in range(100):
                    if len(llamadas) >= 3:
                        break
                    await real_sleep(0.02)
                tarea.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await tarea
        self.assertGreaterEqual(len(llamadas), 3)
