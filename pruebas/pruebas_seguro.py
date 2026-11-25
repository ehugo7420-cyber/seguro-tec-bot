# =============================================================================
# pruebas_seguro.py · Pruebas automáticas (no necesitan token ni internet)
#
# Cada prueba tiene un código (P-01, P-02...) para citarlo en la documentación.
# Se ejecutan con:  python pruebas/pruebas_seguro.py   (o doble clic en probar.bat)
# =============================================================================
import csv
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import almacen  # noqa: E402
import lote  # noqa: E402
from nss import (calcular_digito_verificador, extraer_nss_de_texto, leer_pdf, validar_nss,  # noqa: E402
                 enmascarar)

CONSTANCIAS = RAIZ / "datos_prueba" / "constancias"


def nss_valido(base10: str) -> str:
    return base10 + str(calcular_digito_verificador(base10))


NSS_A = nss_valido("1234567890")
NSS_B = nss_valido("2345678901")
NSS_C = nss_valido("3456789012")


class PruebasNSS(unittest.TestCase):
    def test_P01_nss_valido(self):
        self.assertEqual(validar_nss(NSS_A), (True, ""))

    def test_P02_rechaza_10_digitos(self):
        self.assertFalse(validar_nss("1234567890")[0])

    def test_P03_rechaza_letras(self):
        self.assertFalse(validar_nss("1234567890A")[0])

    def test_P04_rechaza_digito_verificador_incorrecto(self):
        malo = NSS_A[:-1] + str((int(NSS_A[-1]) + 1) % 10)
        valido, motivo = validar_nss(malo)
        self.assertFalse(valido)
        self.assertIn("último dígito", motivo)

    def test_P05_digito_verificador_se_puede_apagar(self):
        malo = NSS_A[:-1] + str((int(NSS_A[-1]) + 1) % 10)
        self.assertTrue(validar_nss(malo, exigir_digito_verificador=False)[0])

    def test_P06_extrae_nss_con_etiqueta(self):
        self.assertEqual(extraer_nss_de_texto(f"Número de Seguridad Social (NSS): {NSS_A}\nOtro: 123"), NSS_A)

    def test_P07_extrae_nss_con_espacios_y_guiones(self):
        texto = "Seguridad Social: 1234 5678-903"
        self.assertEqual(extraer_nss_de_texto(texto), "12345678903")

    def test_P08_dos_numeros_de_11_digitos_sin_etiqueta_es_ambiguo(self):
        self.assertIsNone(extraer_nss_de_texto(f"Folio {NSS_A} y clave {NSS_B}"))

    def test_P09_no_lee_un_numero_de_12_digitos(self):
        self.assertIsNone(extraer_nss_de_texto("Seguridad Social: 123456789012"))

    def test_P10_enmascara_nss(self):
        self.assertEqual(enmascarar("12345678903"), "*******8903")


class PruebasPDF(unittest.TestCase):
    def test_P11_lee_pdf_valido(self):
        self.assertEqual(leer_pdf(CONSTANCIAS / "constancia_prueba_1.pdf"), (NSS_A, "ok"))

    def test_P12_pdf_escaneado_no_tiene_texto(self):
        self.assertEqual(leer_pdf(CONSTANCIAS / "constancia_escaneada.pdf"), (None, "sin_texto"))

    def test_P13_pdf_sin_nss(self):
        self.assertEqual(leer_pdf(CONSTANCIAS / "constancia_sin_nss.pdf"), (None, "no_encontrado"))

    def test_P14_archivo_que_no_es_pdf(self):
        with tempfile.TemporaryDirectory() as d:
            falso = Path(d) / "falso.pdf"
            falso.write_text("esto no es un pdf")
            self.assertEqual(leer_pdf(falso), (None, "pdf_invalido"))


class PruebasBaseDeDatos(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.db = Path(self.dir.name) / "prueba.db"
        almacen.crear_tablas(self.db)

    def tearDown(self):
        self.dir.cleanup()

    def test_P15_guarda_registro_como_pendiente(self):
        almacen.guardar_registro(self.db, 1, "21010001", "ISC", NSS_A)
        r = almacen.registros_de_chat(self.db, 1)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["estado"], almacen.PENDIENTE)

    def test_P16_nss_repetido_con_otro_control_se_rechaza(self):
        almacen.guardar_registro(self.db, 1, "21010001", "ISC", NSS_A)
        with self.assertRaises(almacen.RegistroError):
            almacen.guardar_registro(self.db, 2, "21010002", "ISC", NSS_A)

    def test_P17_control_de_otra_cuenta_se_rechaza(self):
        almacen.guardar_registro(self.db, 1, "21010001", "ISC", NSS_A)
        with self.assertRaises(almacen.RegistroError):
            almacen.guardar_registro(self.db, 2, "21010001", "ISC", NSS_B)

    def test_P18_pendiente_se_puede_corregir(self):
        almacen.guardar_registro(self.db, 1, "21010001", "ISC", NSS_A)
        almacen.guardar_registro(self.db, 1, "21010001", "ISC", NSS_B)
        self.assertEqual(almacen.registros_de_chat(self.db, 1)[0]["nss"], NSS_B)

    def test_P19_lote_incluye_pendientes_y_no_se_repite(self):
        almacen.guardar_registro(self.db, 1, "21010001", "ISC", NSS_A)
        almacen.guardar_registro(self.db, 2, "21010002", "ISC", NSS_B)
        ruta, cantidad = lote.generar_lote(self.db, Path(self.dir.name) / "salidas")
        self.assertEqual(cantidad, 2)
        with open(ruta, encoding="utf-8") as f:
            filas = list(csv.DictReader(f))
        self.assertEqual([x["numero_control"] for x in filas], ["21010001", "21010002"])
        self.assertEqual(almacen.registros_de_chat(self.db, 1)[0]["estado"], almacen.EN_LOTE)
        self.assertEqual(lote.generar_lote(self.db, Path(self.dir.name) / "salidas"), (None, 0))

    def test_P20_en_lote_no_se_puede_cambiar(self):
        almacen.guardar_registro(self.db, 1, "21010001", "ISC", NSS_A)
        lote.generar_lote(self.db, Path(self.dir.name) / "salidas")
        with self.assertRaises(almacen.RegistroError):
            almacen.guardar_registro(self.db, 1, "21010001", "ISC", NSS_B)

    def test_P21_acuse_actualiza_estados(self):
        almacen.guardar_registro(self.db, 1, "21010001", "ISC", NSS_A)
        almacen.guardar_registro(self.db, 2, "21010002", "ISC", NSS_B)
        ruta_acuse = Path(self.dir.name) / "acuse.csv"
        ruta_acuse.write_text(f"nss,resultado,motivo\n{NSS_A},alta,\n{NSS_B},rechazada,Datos distintos\n",
                              encoding="utf-8")
        filas, errores = lote.leer_acuse(ruta_acuse)
        self.assertEqual(errores, [])
        for f in filas:
            almacen.aplicar_acuse(self.db, f["nss"], f["estado"], f["motivo"])
        self.assertEqual(almacen.registros_de_chat(self.db, 1)[0]["estado"], almacen.ASEGURADO)
        rechazado = almacen.registros_de_chat(self.db, 2)[0]
        self.assertEqual((rechazado["estado"], rechazado["motivo"]), (almacen.RECHAZADO, "Datos distintos"))

    def test_P22_acuse_con_resultado_desconocido_se_reporta(self):
        ruta_acuse = Path(self.dir.name) / "acuse.csv"
        ruta_acuse.write_text(f"nss,resultado,motivo\n{NSS_A},quizas,\n", encoding="utf-8")
        filas, errores = lote.leer_acuse(ruta_acuse)
        self.assertEqual(filas, [])
        self.assertEqual(len(errores), 1)

    def test_P23_acuse_con_punto_y_coma_de_excel(self):
        ruta_acuse = Path(self.dir.name) / "acuse.csv"
        ruta_acuse.write_text(f"nss;resultado;motivo\n{NSS_A};alta;\n", encoding="utf-8-sig")
        filas, errores = lote.leer_acuse(ruta_acuse)
        self.assertEqual((len(filas), errores), (1, []))

    def test_P24_acuse_de_nss_inexistente_no_hace_nada(self):
        self.assertIsNone(almacen.aplicar_acuse(self.db, NSS_C, almacen.ASEGURADO))

    def test_P25_recordatorio_solo_a_quien_no_ha_entregado(self):
        almacen.registrar_usuario(self.db, 1)  # no entregó
        almacen.registrar_usuario(self.db, 2)  # sí entregó
        almacen.guardar_registro(self.db, 2, "21010002", "ISC", NSS_B)
        self.assertEqual(almacen.usuarios_para_recordar(self.db, 7), [1])

    def test_P26_recordatorio_respeta_el_intervalo(self):
        almacen.registrar_usuario(self.db, 1)
        almacen.marcar_recordatorio(self.db, 1)
        self.assertEqual(almacen.usuarios_para_recordar(self.db, 7), [])
        en_ocho_dias = datetime.now() + timedelta(days=8)
        self.assertEqual(almacen.usuarios_para_recordar(self.db, 7, ahora=en_ocho_dias), [1])

    def test_P27_tablero_cuenta_por_estado_y_carrera(self):
        almacen.registrar_usuario(self.db, 1)
        almacen.registrar_usuario(self.db, 2)
        almacen.registrar_usuario(self.db, 3)
        almacen.guardar_registro(self.db, 1, "21010001", "ISC", NSS_A)
        almacen.guardar_registro(self.db, 2, "21010002", "Industrial", NSS_B)
        almacen.aplicar_acuse(self.db, NSS_A, almacen.ASEGURADO)
        t = almacen.tablero(self.db)
        self.assertEqual((t["usuarios"], t["sin_nss"]), (3, 1))
        self.assertEqual(t["por_estado"], {almacen.ASEGURADO: 1, almacen.PENDIENTE: 1})
        self.assertEqual(t["por_carrera"]["ISC"], {almacen.ASEGURADO: 1})


if __name__ == "__main__":
    unittest.main(verbosity=2)
