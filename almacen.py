# =============================================================================
# almacen.py · Base de datos (SQLite) del bot
#
# SQLite guarda todo en un solo archivo (seguro.db), sin instalar nada.
# Hay dos tablas:
#   usuarios  -> quién le escribió al bot (para poder mandarle recordatorios)
#   registros -> el NSS que entregó cada alumno y en qué estado va
#
# Estados de un registro:
#   pendiente -> el alumno entregó su NSS, falta incluirlo en un lote
#   en_lote   -> ya salió en un lote que carga el personal en el IMSS
#   asegurado -> el acuse (simulado) dice que el alta quedó
#   rechazado -> el acuse dice que se rechazó; el alumno puede corregirlo
#
# IMPORTANTE: este archivo contiene datos personales. En el prototipo solo se
# usan datos inventados, y seguro.db no se sube a GitHub (ver .gitignore).
# =============================================================================
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta

PENDIENTE = "pendiente"
EN_LOTE = "en_lote"
ASEGURADO = "asegurado"
RECHAZADO = "rechazado"


class RegistroError(Exception):
    """Error que se le puede explicar al alumno con el mensaje que trae."""


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def conectar(ruta):
    con = sqlite3.connect(ruta)
    con.row_factory = sqlite3.Row  # permite leer columnas por nombre
    try:
        yield con
        con.commit()
    finally:
        con.close()


def crear_tablas(ruta):
    with conectar(ruta) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS usuarios (
            chat_id INTEGER PRIMARY KEY,
            primera_vez TEXT,
            ultimo_recordatorio TEXT)""")
        con.execute("""CREATE TABLE IF NOT EXISTS registros (
            numero_control TEXT PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            nss TEXT NOT NULL UNIQUE,
            carrera TEXT,
            estado TEXT NOT NULL,
            motivo TEXT,
            creado TEXT,
            actualizado TEXT)""")


def registrar_usuario(ruta, chat_id: int):
    """Anota que este chat ya le escribió al bot (si ya estaba, no hace nada)."""
    with conectar(ruta) as con:
        con.execute("INSERT OR IGNORE INTO usuarios (chat_id, primera_vez) VALUES (?, ?)",
                    (chat_id, _ahora()))


def guardar_registro(ruta, chat_id: int, numero_control: str, carrera: str, nss: str):
    """Guarda (o corrige) el NSS de un alumno. Lanza RegistroError si no se puede."""
    with conectar(ruta) as con:
        mismo_control = con.execute("SELECT * FROM registros WHERE numero_control = ?",
                                    (numero_control,)).fetchone()
        mismo_nss = con.execute("SELECT numero_control FROM registros WHERE nss = ?", (nss,)).fetchone()

        if mismo_nss and mismo_nss["numero_control"] != numero_control:
            raise RegistroError("Ese NSS ya está registrado con otro número de control. "
                                "Si crees que es un error, acude a Servicios Escolares.")
        if mismo_control:
            if mismo_control["chat_id"] != chat_id:
                # Evita que alguien sobrescriba el registro de otra persona adivinando su número de control.
                raise RegistroError("Ese número de control ya se registró desde otra cuenta. "
                                    "Acude a Servicios Escolares.")
            if mismo_control["estado"] == ASEGURADO:
                raise RegistroError("Ya estás dado de alta, no necesitas entregar tu NSS otra vez.")
            if mismo_control["estado"] == EN_LOTE:
                raise RegistroError("Tu alta ya va en proceso. Espera el aviso del resultado.")
            con.execute("""UPDATE registros SET nss = ?, carrera = ?, estado = ?, motivo = NULL, actualizado = ?
                           WHERE numero_control = ?""", (nss, carrera, PENDIENTE, _ahora(), numero_control))
        else:
            con.execute("""INSERT INTO registros (numero_control, chat_id, nss, carrera, estado, creado, actualizado)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (numero_control, chat_id, nss, carrera, PENDIENTE, _ahora(), _ahora()))


def registros_de_chat(ruta, chat_id: int) -> list:
    with conectar(ruta) as con:
        filas = con.execute("SELECT * FROM registros WHERE chat_id = ? ORDER BY creado", (chat_id,)).fetchall()
        return [dict(f) for f in filas]


def pendientes_para_lote(ruta) -> list:
    with conectar(ruta) as con:
        filas = con.execute("SELECT * FROM registros WHERE estado = ? ORDER BY numero_control",
                            (PENDIENTE,)).fetchall()
        return [dict(f) for f in filas]


def marcar_en_lote(ruta, controles: list):
    with conectar(ruta) as con:
        for control in controles:
            con.execute("UPDATE registros SET estado = ?, actualizado = ? WHERE numero_control = ?",
                        (EN_LOTE, _ahora(), control))


def aplicar_acuse(ruta, nss: str, estado: str, motivo: str = ""):
    """Aplica el resultado del IMSS a un NSS. Devuelve {'chat_id', 'numero_control'} o None si no existe."""
    with conectar(ruta) as con:
        fila = con.execute("SELECT * FROM registros WHERE nss = ? AND estado IN (?, ?)",
                           (nss, PENDIENTE, EN_LOTE)).fetchone()
        if not fila:
            return None
        con.execute("UPDATE registros SET estado = ?, motivo = ?, actualizado = ? WHERE numero_control = ?",
                    (estado, motivo or None, _ahora(), fila["numero_control"]))
        return {"chat_id": fila["chat_id"], "numero_control": fila["numero_control"]}


def usuarios_para_recordar(ruta, cada_dias: int, ahora=None) -> list:
    """Chats que le escribieron al bot pero todavía no entregan su NSS y
    a quienes no se les ha recordado en los últimos `cada_dias` días."""
    ahora = ahora or datetime.now()
    with conectar(ruta) as con:
        filas = con.execute("""SELECT chat_id, ultimo_recordatorio FROM usuarios u
                               WHERE NOT EXISTS (SELECT 1 FROM registros r WHERE r.chat_id = u.chat_id)""").fetchall()
    elegidos = []
    for fila in filas:
        ultimo = fila["ultimo_recordatorio"]
        if ultimo is None or ahora - datetime.fromisoformat(ultimo) >= timedelta(days=cada_dias):
            elegidos.append(fila["chat_id"])
    return elegidos


def marcar_recordatorio(ruta, chat_id: int):
    with conectar(ruta) as con:
        con.execute("UPDATE usuarios SET ultimo_recordatorio = ? WHERE chat_id = ?", (_ahora(), chat_id))


def tablero(ruta) -> dict:
    """Números para la jefatura: totales por estado y por carrera (sin nombres ni NSS)."""
    with conectar(ruta) as con:
        usuarios = con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
        sin_nss = con.execute("""SELECT COUNT(*) FROM usuarios u
                                 WHERE NOT EXISTS (SELECT 1 FROM registros r WHERE r.chat_id = u.chat_id)""").fetchone()[0]
        por_estado = {f["estado"]: f["n"] for f in
                      con.execute("SELECT estado, COUNT(*) AS n FROM registros GROUP BY estado")}
        por_carrera = {}
        for f in con.execute("SELECT carrera, estado, COUNT(*) AS n FROM registros GROUP BY carrera, estado"):
            datos = por_carrera.setdefault(f["carrera"] or "Sin carrera", {})
            datos[f["estado"]] = f["n"]
    return {"usuarios": usuarios, "sin_nss": sin_nss, "por_estado": por_estado, "por_carrera": por_carrera}
