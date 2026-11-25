# =============================================================================
# SeguroTec · Bot de Telegram para entregar el NSS y dar seguimiento al alta
# en el seguro facultativo del IMSS (prototipo escolar, con datos de ejemplo).
#
# Qué hace:
#   ALUMNO
#   - Menú con botones al escribir /start.
#   - "Subir mi NSS": pide número de control, carrera y el PDF de la constancia
#     (o el NSS escrito), lo lee, lo valida y pide confirmación.
#   - "Mi estado": dice si está pendiente, en proceso, asegurado o rechazado.
#   - Recordatorio automático a quien le escribió al bot y no ha entregado su NSS.
#   PERSONAL AUTORIZADO (IDs en ADMIN_IDS del archivo .env)
#   - /lote       -> genera el archivo CSV de altas pendientes.
#   - /acuse_demo -> lee el acuse simulado y avisa a cada alumno.
#     (o enviar un archivo .csv con el acuse al chat del bot)
#   - /recordar   -> manda los recordatorios en este momento.
#   - /tablero    -> totales por estado y por carrera.
#
# El bot NUNCA se conecta al IMSS: cargar el lote en la plataforma es un paso humano.
# =============================================================================
import html
import json
import logging
import os
import unicodedata
from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, LinkPreviewOptions
from telegram.constants import ChatAction, ParseMode
from telegram.error import TimedOut, NetworkError
from telegram.ext import (Application, CommandHandler, MessageHandler, CallbackQueryHandler,
                          ContextTypes, filters)

import almacen
import lote
from nss import leer_pdf, validar_nss, solo_digitos, enmascarar

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN GENERAL
# -----------------------------------------------------------------------------
CARPETA = Path(__file__).parent
ARCHIVO_CONFIG = CARPETA / "config.json"            # lo edita el personal del área
RUTA_DB = Path(os.getenv("RUTA_DB", CARPETA / "seguro.db"))
CARPETA_SALIDAS = CARPETA / "salidas"               # aquí se guardan los lotes
CARPETA_TEMP = CARPETA / "temp"                     # PDFs que se borran al leerlos
ACUSE_DEMO = CARPETA / "datos_prueba" / "acuse_simulado.csv"
ZONA = ZoneInfo("America/Mexico_City")

load_dotenv(CARPETA / ".env")                       # lee el archivo .env
TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()     # token que da @BotFather
ADMINS = {x.strip() for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()}

logging.basicConfig(format="%(asctime)s · %(levelname)s · %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("seguro")  # OJO: en los logs nunca se escribe un NSS completo


def cargar_config() -> dict:
    """Lee config.json cada vez que hace falta: si el área lo cambia, el bot usa lo nuevo sin reiniciarse."""
    with open(ARCHIVO_CONFIG, encoding="utf-8") as f:
        return json.load(f)


def normalizar(texto: str) -> str:
    """Minúsculas y sin acentos: 'ESTADO' -> 'estado'."""
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn").strip()


def es_admin(update: Update) -> bool:
    return bool(update.effective_user) and str(update.effective_user.id) in ADMINS


# -----------------------------------------------------------------------------
# 2. TEXTOS Y BOTONES
# -----------------------------------------------------------------------------
def teclado(*filas):
    """Arma botones. Cada fila es una lista de (texto, codigo). Si el código empieza con http, abre un link."""
    return InlineKeyboardMarkup([[InlineKeyboardButton(t, url=c) if c.startswith("http")
                                  else InlineKeyboardButton(t, callback_data=c) for t, c in fila] for fila in filas])


MENU = teclado([("📤 Subir mi NSS", "subir")],
               [("🔎 Mi estado", "estado"), ("🧭 ¿Cómo saco mi NSS?", "como")],
               [("❓ Ayuda", "ayuda")])
SOLO_MENU = teclado([("🏠 Volver al menú", "menu")])

ETIQUETA_ESTADO = {
    almacen.PENDIENTE: "🕒 Pendiente: ya tenemos tu NSS y falta incluirlo en el siguiente lote.",
    almacen.EN_LOTE: "📨 En proceso: tu alta ya fue enviada al IMSS y esperamos el resultado.",
    almacen.ASEGURADO: "✅ Asegurado: tu alta quedó registrada.",
    almacen.RECHAZADO: "⚠️ Rechazado: hay que corregir algo.",
}

# Palabras que el alumno puede escribir en lugar de tocar botones (ya sin acentos)
PALABRAS = [
    (("nss", "subir", "entregar", "alta", "constancia"), "subir"),
    (("estado", "asegurado", "vigencia", "seguimiento"), "estado"),
    (("como", "obtener", "sacar"), "como"),
    (("ayuda", "info", "informacion"), "ayuda"),
    (("hola", "menu", "inicio", "buenas"), "menu"),
]


async def enviar(update: Update, texto: str, botones=None):
    """Responde en el chat mostrando antes 'escribiendo…'."""
    chat = update.effective_chat
    await chat.send_action(ChatAction.TYPING)
    await chat.send_message(texto, reply_markup=botones, parse_mode=ParseMode.HTML,
                            link_preview_options=LinkPreviewOptions(is_disabled=True))


# -----------------------------------------------------------------------------
# 3. FLUJO DEL ALUMNO
#    Para saber en qué paso va cada persona usamos context.user_data["paso"]:
#    None -> control -> carrera -> pdf -> confirmar
# -----------------------------------------------------------------------------
async def bienvenida(update: Update, context: ContextTypes.DEFAULT_TYPE):  # /start
    context.user_data.clear()
    almacen.registrar_usuario(RUTA_DB, update.effective_chat.id)
    cfg = cargar_config()
    await enviar(update,
                 "<b>¡Hola! 👋</b>\n"
                 f"Soy el asistente del <b>seguro facultativo del IMSS</b> de {html.escape(cfg['nombre_institucion'])}.\n\n"
                 "Aquí puedes entregar tu NSS sin hacer fila, saber si ya estás dado de alta y recibir avisos.\n\n"
                 "<i>Prototipo escolar con datos de ejemplo: no uses tus datos reales.</i>\n\n"
                 "👇 <b>Elige una opción:</b>", MENU)


async def mostrar_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["paso"] = None
    await enviar(update, "🏠 <b>Menú principal</b>\n¿Qué necesitas?", MENU)


async def pedir_control(update: Update, context: ContextTypes.DEFAULT_TYPE):  # botón "Subir mi NSS"
    almacen.registrar_usuario(RUTA_DB, update.effective_chat.id)
    context.user_data.clear()
    context.user_data["paso"] = "control"
    n = cargar_config()["longitud_numero_control"]
    await enviar(update, f"📤 <b>Paso 1 de 3 · Número de control</b>\n\nEscribe tu número de control ({n} dígitos).")


async def recibir_control(update: Update, context: ContextTypes.DEFAULT_TYPE, texto: str):
    cfg = cargar_config()
    n = cfg["longitud_numero_control"]
    if not (texto.isdigit() and len(texto) == n):
        await enviar(update, f"🤔 El número de control debe tener <b>{n} dígitos</b> y solo números. Intenta de nuevo.")
        return
    context.user_data["control"] = texto
    context.user_data["paso"] = "carrera"
    botones = teclado(*[[(c, f"car:{i}")] for i, c in enumerate(cfg["carreras"])])
    await enviar(update, "🎓 <b>Paso 2 de 3 · Carrera</b>\n\nElige tu carrera:", botones)


async def elegir_carrera(update: Update, context: ContextTypes.DEFAULT_TYPE, indice: int):
    carreras = cargar_config()["carreras"]
    if context.user_data.get("paso") != "carrera" or not (0 <= indice < len(carreras)):
        await mostrar_menu(update, context)
        return
    context.user_data["carrera"] = carreras[indice]
    context.user_data["paso"] = "pdf"
    await enviar(update, "📎 <b>Paso 3 de 3 · Tu constancia</b>\n\n"
                         "Mándame el <b>PDF</b> de tu constancia del IMSS.\n"
                         "Si solo tienes foto, escribe tu NSS (11 dígitos) aquí en el chat.")


async def pedir_confirmacion(update: Update, context: ContextTypes.DEFAULT_TYPE, nss: str):
    """Valida el NSS y, si está bien, le pide al alumno que confirme lo que se leyó."""
    cfg = cargar_config()
    valido, motivo = validar_nss(nss, cfg.get("validar_digito_verificador", True))
    if not valido:
        await enviar(update, f"⚠️ <b>No pude aceptar ese NSS.</b>\n{html.escape(motivo)}\n\n"
                             "Revisa tu constancia y mándala de nuevo, o escribe tu NSS.")
        return
    context.user_data["nss"] = nss
    context.user_data["paso"] = "confirmar"
    await enviar(update, f"🔍 <b>Esto fue lo que leí</b>\n\nNSS: <code>{nss}</code>\n\n<b>¿Es correcto?</b>",
                 teclado([("👍 Sí, es correcto", "nss_si"), ("👎 No", "nss_no")]))


async def confirmar_si(update: Update, context: ContextTypes.DEFAULT_TYPE):
    datos = context.user_data
    if datos.get("paso") != "confirmar":
        await mostrar_menu(update, context)
        return
    try:
        almacen.guardar_registro(RUTA_DB, update.effective_chat.id, datos["control"], datos["carrera"], datos["nss"])
    except almacen.RegistroError as e:
        datos["paso"] = None
        await enviar(update, f"⚠️ {html.escape(str(e))}", SOLO_MENU)
        return
    log.info("NSS registrado (%s) para el control %s", enmascarar(datos["nss"]), datos["control"])
    context.user_data.clear()
    await enviar(update, "🎉 <b>¡Listo!</b> Tu NSS quedó registrado.\n\n"
                         "El personal de Servicios Escolares lo incluirá en el siguiente lote de altas y "
                         "<b>te avisaré aquí</b> cuando haya resultado.", teclado([("🔎 Mi estado", "estado"), ("🏠 Menú", "menu")]))


async def confirmar_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["paso"] = "pdf"
    context.user_data.pop("nss", None)
    await enviar(update, "👌 Sin problema. Mándame otra vez el PDF o escribe tu NSS (11 dígitos).")


async def mostrar_estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    registros = almacen.registros_de_chat(RUTA_DB, update.effective_chat.id)
    if not registros:
        await enviar(update, "🔎 Todavía no has entregado tu NSS.", teclado([("📤 Subir mi NSS", "subir"), ("🏠 Menú", "menu")]))
        return
    partes = ["🔎 <b>Tu estado</b>"]
    for r in registros:
        partes.append(f"\nControl <code>{html.escape(r['numero_control'])}</code>\n{ETIQUETA_ESTADO[r['estado']]}")
        if r["estado"] == almacen.RECHAZADO and r["motivo"]:
            partes.append(f"Motivo: {html.escape(r['motivo'])}")
    hay_rechazo = any(r["estado"] == almacen.RECHAZADO for r in registros)
    botones = teclado([("📤 Corregir mi NSS", "subir")] if hay_rechazo else [("🏠 Menú", "menu")])
    await enviar(update, "\n".join(partes), botones)


async def mostrar_como(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = cargar_config()
    await enviar(update, "🧭 <b>¿Cómo saco mi NSS?</b>\n\n"
                         "1️⃣ Entra al portal del IMSS para estudiantes (solo necesitas tu CURP y tu correo).\n"
                         "2️⃣ Descarga tu constancia en PDF.\n"
                         "3️⃣ Regresa aquí y toca <b>Subir mi NSS</b>.\n\n"
                         "Para ver si ya estás vigente usa el enlace de vigencia.",
                 teclado([("🌐 Portal del IMSS", cfg["enlace_nss"])], [("✅ Consultar vigencia", cfg["enlace_vigencia"])],
                         [("📤 Subir mi NSS", "subir"), ("🏠 Menú", "menu")]))


async def mostrar_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await enviar(update, "❓ <b>Ayuda</b>\n\nToca los botones o escribe: <b>nss</b> · <b>estado</b> · <b>cómo</b>.\n\n"
                         "ℹ️ Este bot solo recibe tu NSS y te avisa el resultado. La alta la carga el personal de "
                         "Servicios Escolares en la plataforma del IMSS.\n\n"
                         "<i>Prototipo escolar con datos de ejemplo.</i>", MENU)


async def no_entendi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await enviar(update, "🤔 <b>No entendí tu mensaje.</b>\nElige una opción o escribe, por ejemplo, «nss».", MENU)


ACCIONES = {"menu": mostrar_menu, "subir": pedir_control, "estado": mostrar_estado, "como": mostrar_como,
            "ayuda": mostrar_ayuda, "nss_si": confirmar_si, "nss_no": confirmar_no}


# -----------------------------------------------------------------------------
# 4. RECIBIR BOTONES, TEXTOS Y ARCHIVOS
# -----------------------------------------------------------------------------
async def boton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Se ejecuta cuando alguien toca un botón."""
    consulta = update.callback_query
    await consulta.answer()
    try:  # quita los botones ya usados para que el chat quede limpio
        await consulta.edit_message_reply_markup(None)
    except Exception:
        pass
    if consulta.data.startswith("car:"):
        await elegir_carrera(update, context, int(consulta.data.split(":")[1]))
        return
    await ACCIONES.get(consulta.data, no_entendi)(update, context)


async def texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Se ejecuta cuando alguien escribe un mensaje."""
    t = update.message.text.strip()
    paso = context.user_data.get("paso")
    if paso == "control":
        return await recibir_control(update, context, t)
    if paso == "pdf":  # en este paso también se acepta el NSS escrito a mano
        return await pedir_confirmacion(update, context, solo_digitos(t))
    palabra = normalizar(t)
    for claves, opcion in PALABRAS:
        if any(c in palabra for c in claves):
            return await ACCIONES[opcion](update, context)
    await no_entendi(update, context)


async def archivo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Se ejecuta cuando alguien manda un documento: PDF del alumno o CSV del personal."""
    doc = update.message.document
    nombre = (doc.file_name or "").lower()
    if es_admin(update) and nombre.endswith(".csv"):
        return await acuse_desde_archivo(update, context, doc)
    if context.user_data.get("paso") != "pdf":
        await enviar(update, "📎 Para entregar tu NSS primero toca <b>Subir mi NSS</b>.", MENU)
        return
    if not (nombre.endswith(".pdf") or doc.mime_type == "application/pdf"):
        await enviar(update, "📎 Solo puedo leer archivos <b>PDF</b>. También puedes escribir tu NSS.")
        return
    limite_mb = cargar_config().get("tamano_maximo_pdf_mb", 5)
    if doc.file_size and doc.file_size > limite_mb * 1024 * 1024:
        await enviar(update, f"📎 El archivo pesa demasiado (máximo {limite_mb} MB).")
        return
    CARPETA_TEMP.mkdir(exist_ok=True)
    ruta = CARPETA_TEMP / f"{update.effective_chat.id}_{doc.file_unique_id}.pdf"
    try:
        descargado = await doc.get_file()
        await descargado.download_to_drive(custom_path=ruta)
        nss, motivo = leer_pdf(ruta)
    finally:
        ruta.unlink(missing_ok=True)  # el PDF se borra siempre: solo guardamos el NSS confirmado
    if nss is None:
        explicacion = {"sin_texto": "Parece una foto o un PDF escaneado y no puedo leerlo.",
                       "no_encontrado": "No encontré un NSS claro en el documento.",
                       "pdf_invalido": "El archivo no se pudo abrir como PDF."}[motivo]
        await enviar(update, f"⚠️ {explicacion}\nEscribe tu NSS (11 dígitos) aquí en el chat.")
        return
    await pedir_confirmacion(update, context, nss)


# -----------------------------------------------------------------------------
# 5. PERSONAL DEL ÁREA (solo IDs de ADMIN_IDS)
# -----------------------------------------------------------------------------
async def solo_personal(update: Update) -> bool:
    if es_admin(update):
        return True
    await enviar(update, "🔒 Este comando es solo para el personal del área.")
    return False


async def comando_lote(update: Update, context: ContextTypes.DEFAULT_TYPE):  # /lote
    if not await solo_personal(update):
        return
    ruta, cantidad = lote.generar_lote(RUTA_DB, CARPETA_SALIDAS)
    if ruta is None:
        await enviar(update, "📭 No hay altas pendientes.")
        return
    with open(ruta, "rb") as f:
        await update.effective_chat.send_document(f, filename=ruta.name,
                                                  caption=f"📦 Lote con {cantidad} alta(s). Cárgalo en la plataforma del IMSS.")


async def aplicar_acuse(bot, ruta_csv) -> str:
    """Lee el acuse, actualiza a cada alumno y le avisa. Devuelve un resumen para el personal."""
    cfg = cargar_config()
    filas, errores = lote.leer_acuse(ruta_csv)
    altas = rechazos = sin_registro = sin_aviso = 0
    for fila in filas:
        resultado = almacen.aplicar_acuse(RUTA_DB, fila["nss"], fila["estado"], fila["motivo"])
        if resultado is None:
            sin_registro += 1
            continue
        if fila["estado"] == almacen.ASEGURADO:
            altas += 1
            aviso = ("✅ <b>¡Ya estás dado de alta!</b>\nTu NSS quedó registrado en el seguro facultativo.\n"
                     f'Puedes revisar tu vigencia <a href="{cfg["enlace_vigencia"]}">aquí</a> '
                     "(puede tardar en reflejarse).")
            botones = None
        else:
            rechazos += 1
            aviso = (f"⚠️ <b>Tu alta fue rechazada.</b>\nMotivo: {html.escape(fila['motivo'])}\n"
                     "Toca el botón para corregir tu NSS.")
            botones = teclado([("📤 Corregir mi NSS", "subir")])
        try:
            await bot.send_message(resultado["chat_id"], aviso, reply_markup=botones, parse_mode=ParseMode.HTML)
        except Exception as e:  # por ejemplo, si el alumno bloqueó el bot
            sin_aviso += 1
            log.warning("No se pudo avisar al control %s: %s", resultado["numero_control"], e)
    resumen = (f"📥 <b>Acuse procesado</b>\n✅ Altas: {altas}\n⚠️ Rechazos: {rechazos}\n"
               f"❔ NSS sin registro pendiente: {sin_registro}\n🔕 Sin poder avisar: {sin_aviso}")
    if errores:
        resumen += "\n\n<b>Renglones con problema:</b>\n" + "\n".join(html.escape(e) for e in errores[:10])
    return resumen


async def comando_acuse_demo(update: Update, context: ContextTypes.DEFAULT_TYPE):  # /acuse_demo
    if not await solo_personal(update):
        return
    if not ACUSE_DEMO.exists():
        await enviar(update, "No encontré datos_prueba/acuse_simulado.csv.")
        return
    await enviar(update, await aplicar_acuse(context.bot, ACUSE_DEMO))


async def acuse_desde_archivo(update: Update, context: ContextTypes.DEFAULT_TYPE, doc):
    CARPETA_TEMP.mkdir(exist_ok=True)
    ruta = CARPETA_TEMP / f"acuse_{doc.file_unique_id}.csv"
    try:
        descargado = await doc.get_file()
        await descargado.download_to_drive(custom_path=ruta)
        resumen = await aplicar_acuse(context.bot, ruta)
    finally:
        ruta.unlink(missing_ok=True)
    await enviar(update, resumen)


async def enviar_recordatorios(bot, forzar: bool = False) -> int:
    """Recuerda a quien le escribió al bot pero no ha entregado su NSS. Devuelve cuántos avisos salieron."""
    cada_dias = 0 if forzar else cargar_config().get("recordatorio_cada_dias", 7)
    enviados = 0
    for chat_id in almacen.usuarios_para_recordar(RUTA_DB, cada_dias):
        try:
            await bot.send_message(chat_id, "🔔 <b>Recordatorio</b>\n\nAún no has entregado tu NSS para el seguro "
                                            "facultativo del IMSS. Sin él no podemos darte de alta.",
                                   reply_markup=teclado([("📤 Subir mi NSS", "subir")]), parse_mode=ParseMode.HTML)
            almacen.marcar_recordatorio(RUTA_DB, chat_id)
            enviados += 1
        except Exception as e:
            log.warning("No se pudo recordar al chat %s: %s", chat_id, e)
    return enviados


async def recordatorio_diario(context: ContextTypes.DEFAULT_TYPE):
    """La ejecuta el programador de tareas todos los días a la hora de config.json."""
    enviados = await enviar_recordatorios(context.bot)
    log.info("Recordatorios enviados: %d", enviados)


async def comando_recordar(update: Update, context: ContextTypes.DEFAULT_TYPE):  # /recordar
    if not await solo_personal(update):
        return
    enviados = await enviar_recordatorios(context.bot, forzar=True)
    await enviar(update, f"🔔 Recordatorios enviados: <b>{enviados}</b>.")


async def comando_tablero(update: Update, context: ContextTypes.DEFAULT_TYPE):  # /tablero
    if not await solo_personal(update):
        return
    t = almacen.tablero(RUTA_DB)
    e = t["por_estado"]
    pendientes = e.get(almacen.PENDIENTE, 0) + e.get(almacen.EN_LOTE, 0)
    partes = ["📊 <b>Tablero</b>",
              f"Alumnos que escribieron al bot: {t['usuarios']}",
              f"Sin entregar NSS: {t['sin_nss']}",
              f"✅ Asegurados: {e.get(almacen.ASEGURADO, 0)}",
              f"⚠️ Rechazados: {e.get(almacen.RECHAZADO, 0)}",
              f"🕒 En trámite: {pendientes}", "", "<b>Por carrera</b>"]
    for carrera, d in sorted(t["por_carrera"].items()):
        partes.append(f"{html.escape(carrera)}: {d.get(almacen.ASEGURADO, 0)} asegurados, "
                      f"{d.get(almacen.RECHAZADO, 0)} rechazados, "
                      f"{d.get(almacen.PENDIENTE, 0) + d.get(almacen.EN_LOTE, 0)} en trámite")
    await enviar(update, "\n".join(partes))


async def mi_id(update: Update, context: ContextTypes.DEFAULT_TYPE):  # /miid
    """Muestra tu ID de Telegram para ponerlo en ADMIN_IDS del archivo .env."""
    await enviar(update, f"🪪 Tu ID de Telegram es: <code>{update.effective_user.id}</code>")


# -----------------------------------------------------------------------------
# 6. ARRANQUE
# -----------------------------------------------------------------------------
async def al_iniciar(app: Application):
    await app.bot.set_my_commands([BotCommand("start", "Inicio y menú principal"),
                                   BotCommand("menu", "Volver al menú")])


async def error(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Si algo falla, lo anota en la terminal y le avisa al usuario con un mensaje claro."""
    if isinstance(context.error, (TimedOut, NetworkError)):  # internet lento: el bot reintenta solo
        log.warning("Internet lento o sin conexión (%s). El bot sigue funcionando.", context.error)
        return
    log.error("Error: %s", context.error)
    if isinstance(update, Update) and update.effective_chat:
        await update.effective_chat.send_message("⚠️ Ocurrió un problema. Intenta de nuevo o escribe «menú».")


def crear_app(token: str) -> Application:
    app = (Application.builder().token(token).post_init(al_iniciar)
           .connect_timeout(15).read_timeout(20).write_timeout(20).build())
    app.add_handler(CommandHandler("start", bienvenida))
    app.add_handler(CommandHandler("menu", mostrar_menu))
    app.add_handler(CommandHandler("lote", comando_lote))
    app.add_handler(CommandHandler("acuse_demo", comando_acuse_demo))
    app.add_handler(CommandHandler("recordar", comando_recordar))
    app.add_handler(CommandHandler("tablero", comando_tablero))
    app.add_handler(CommandHandler("miid", mi_id))
    app.add_handler(CallbackQueryHandler(boton))
    app.add_handler(MessageHandler(filters.Document.ALL, archivo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, texto))
    app.add_error_handler(error)
    hora, minuto = (int(x) for x in cargar_config().get("hora_recordatorio", "09:00").split(":"))
    app.job_queue.run_daily(recordatorio_diario, time=time(hora, minuto, tzinfo=ZONA), name="recordatorios")
    return app


def main():
    if not TOKEN:
        raise SystemExit("Falta el token. Crea el archivo .env con la línea TELEGRAM_TOKEN=tu_token (ver GUIA.md).")
    cargar_config()  # revisa que config.json exista y esté bien escrito
    almacen.crear_tablas(RUTA_DB)
    log.info("Bot encendido. Presiona Ctrl + C para apagarlo.")
    crear_app(TOKEN).run_polling()


if __name__ == "__main__":
    main()
