# =============================================================================
# pruebas_bot.py · Pruebas del flujo del bot con "chats falsos"
#
# No se conectan a Telegram: simulan un chat que guarda los mensajes que el bot
# manda, para revisar que cada paso responde lo correcto. Necesitan tener
# instalado python-telegram-bot (pip install -r requirements.txt), pero NO
# necesitan token ni internet.
# Se ejecutan con:  python pruebas/pruebas_bot.py
# =============================================================================
import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

try:
    import bot
    HAY_TELEGRAM = True
except ImportError:  # no está instalado python-telegram-bot
    HAY_TELEGRAM = False

import almacen  # noqa: E402
from nss import calcular_digito_verificador  # noqa: E402

NSS_A = "1234567890" + str(calcular_digito_verificador("1234567890"))
NSS_MALO = NSS_A[:-1] + str((int(NSS_A[-1]) + 1) % 10)


# ---- Objetos falsos que imitan lo mínimo de Telegram ------------------------
class ChatFalso:
    def __init__(self, chat_id):
        self.id = chat_id
        self.mensajes, self.documentos = [], []

    async def send_action(self, accion):
        pass

    async def send_message(self, texto, **kw):
        self.mensajes.append(texto)

    async def send_document(self, archivo, **kw):
        self.documentos.append(kw.get("filename"))


class UsuarioFalso:
    def __init__(self, user_id):
        self.id = user_id


class MensajeFalso:
    def __init__(self, texto):
        self.text = texto


class ConsultaFalsa:
    def __init__(self, data):
        self.data = data

    async def answer(self):
        pass

    async def edit_message_reply_markup(self, markup):
        pass


class ActualizacionFalsa:
    def __init__(self, chat, usuario, texto=None, boton=None):
        self.effective_chat = chat
        self.effective_user = usuario
        self.message = MensajeFalso(texto) if texto is not None else None
        self.callback_query = ConsultaFalsa(boton) if boton is not None else None


class ContextoFalso:
    def __init__(self, bot_falso=None):
        self.user_data = {}
        self.bot = bot_falso


class BotFalso:
    def __init__(self):
        self.enviados = []  # (chat_id, texto)

    async def send_message(self, chat_id, texto, **kw):
        self.enviados.append((chat_id, texto))


def correr(corutina):
    return asyncio.run(corutina)


@unittest.skipUnless(HAY_TELEGRAM, "falta instalar python-telegram-bot")
class PruebasFlujo(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        bot.RUTA_DB = Path(self.dir.name) / "prueba.db"
        bot.CARPETA_SALIDAS = Path(self.dir.name) / "salidas"
        bot.ADMINS = {"999"}
        almacen.crear_tablas(bot.RUTA_DB)
        self.chat, self.user, self.ctx = ChatFalso(1), UsuarioFalso(1), ContextoFalso()

    def tearDown(self):
        self.dir.cleanup()

    def alumno_dice(self, texto=None, boton=None):
        """Simula que el alumno escribe un texto o toca un botón."""
        act = ActualizacionFalsa(self.chat, self.user, texto=texto, boton=boton)
        correr(bot.boton(act, self.ctx) if boton is not None else bot.texto(act, self.ctx))

    def registrar_alumno(self, control="21010001", nss=NSS_A):
        correr(bot.bienvenida(ActualizacionFalsa(self.chat, self.user), self.ctx))
        self.alumno_dice(boton="subir")
        self.alumno_dice(texto=control)
        self.alumno_dice(boton="car:0")
        self.alumno_dice(texto=nss)
        self.alumno_dice(boton="nss_si")

    def test_F01_start_registra_al_usuario_y_muestra_menu(self):
        correr(bot.bienvenida(ActualizacionFalsa(self.chat, self.user), self.ctx))
        self.assertIn("seguro facultativo", self.chat.mensajes[-1])
        self.assertEqual(almacen.tablero(bot.RUTA_DB)["usuarios"], 1)

    def test_F02_flujo_completo_deja_el_registro_pendiente(self):
        self.registrar_alumno()
        registro = almacen.registros_de_chat(bot.RUTA_DB, 1)[0]
        self.assertEqual((registro["numero_control"], registro["nss"], registro["estado"]),
                         ("21010001", NSS_A, almacen.PENDIENTE))
        self.assertIn("quedó registrado", self.chat.mensajes[-1])

    def test_F03_numero_de_control_invalido_se_vuelve_a_pedir(self):
        self.alumno_dice(boton="subir")
        self.alumno_dice(texto="123")
        self.assertEqual(self.ctx.user_data["paso"], "control")
        self.assertIn("dígitos", self.chat.mensajes[-1])

    def test_F04_nss_con_digito_verificador_malo_no_pide_confirmacion(self):
        self.alumno_dice(boton="subir")
        self.alumno_dice(texto="21010001")
        self.alumno_dice(boton="car:0")
        self.alumno_dice(texto=NSS_MALO)
        self.assertIn("No pude aceptar", self.chat.mensajes[-1])
        self.assertEqual(self.ctx.user_data["paso"], "pdf")

    def test_F05_comando_de_personal_se_niega_a_un_alumno(self):
        act = ActualizacionFalsa(self.chat, self.user)
        correr(bot.comando_lote(act, self.ctx))
        self.assertIn("solo para el personal", self.chat.mensajes[-1])

    def test_F06_personal_genera_lote_y_el_acuse_avisa_al_alumno(self):
        self.registrar_alumno()
        personal = ChatFalso(999)
        act = ActualizacionFalsa(personal, UsuarioFalso(999))
        correr(bot.comando_lote(act, ContextoFalso()))
        self.assertEqual(len(personal.documentos), 1)
        self.assertEqual(almacen.registros_de_chat(bot.RUTA_DB, 1)[0]["estado"], almacen.EN_LOTE)

        acuse = Path(self.dir.name) / "acuse.csv"
        acuse.write_text(f"nss,resultado,motivo\n{NSS_A},rechazada,Datos distintos\n", encoding="utf-8")
        bot_falso = BotFalso()
        resumen = correr(bot.aplicar_acuse(bot_falso, acuse))
        self.assertIn("Rechazos: 1", resumen)
        self.assertEqual(bot_falso.enviados[0][0], 1)
        self.assertIn("rechazada", bot_falso.enviados[0][1])

        self.alumno_dice(boton="estado")  # el alumno ve el motivo del rechazo
        self.assertIn("Datos distintos", self.chat.mensajes[-1])

    def test_F07_recordatorio_solo_a_quien_no_ha_entregado(self):
        correr(bot.bienvenida(ActualizacionFalsa(self.chat, self.user), self.ctx))  # escribió, no entregó
        otro = ChatFalso(2)
        otro_user = UsuarioFalso(2)
        correr(bot.bienvenida(ActualizacionFalsa(otro, otro_user), ContextoFalso()))
        almacen.guardar_registro(bot.RUTA_DB, 2, "21010002", "ISC", NSS_A)  # el chat 2 sí entregó
        bot_falso = BotFalso()
        enviados = correr(bot.enviar_recordatorios(bot_falso))
        self.assertEqual(enviados, 1)
        self.assertEqual(bot_falso.enviados[0][0], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
