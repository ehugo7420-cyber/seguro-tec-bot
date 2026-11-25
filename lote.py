# =============================================================================
# lote.py · Arma el lote de altas y lee el acuse del IMSS (simulado)
#
# El bot NO se conecta al IMSS. Lo único que hace es:
#   - generar_lote(): crea un archivo CSV con los alumnos pendientes. El
#     personal autorizado lo carga en la plataforma del IMSS (paso humano).
#   - leer_acuse(): lee el archivo CSV con el resultado (aquí es un archivo de
#     ejemplo) para marcar a cada alumno como asegurado o rechazado.
# El formato real del lote lo debe confirmar Servicios Escolares; aquí es un
# ejemplo con dos columnas.
# =============================================================================
import csv
import unicodedata
from datetime import datetime
from pathlib import Path

import almacen

_ALTA = {"alta", "asegurado", "aceptada", "aceptado", "ok"}
_RECHAZO = {"rechazada", "rechazado", "rechazo", "error"}


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn").strip()


def generar_lote(ruta_db, carpeta_salida, ahora=None):
    """Crea el CSV con los pendientes y los marca 'en_lote'. Devuelve (ruta, cantidad).
    Si no hay pendientes devuelve (None, 0)."""
    pendientes = almacen.pendientes_para_lote(ruta_db)
    if not pendientes:
        return None, 0
    ahora = ahora or datetime.now()
    carpeta = Path(carpeta_salida)
    carpeta.mkdir(exist_ok=True)
    ruta = carpeta / f"lote_{ahora.strftime('%Y%m%d_%H%M%S')}.csv"
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(["numero_control", "nss"])
        for fila in pendientes:
            escritor.writerow([fila["numero_control"], fila["nss"]])
    almacen.marcar_en_lote(ruta_db, [fila["numero_control"] for fila in pendientes])
    return ruta, len(pendientes)


def leer_acuse(ruta_csv):
    """Lee el acuse (columnas: nss, resultado, motivo).
    Devuelve (filas_validas, errores). Cada fila válida: {'nss', 'estado', 'motivo'}."""
    filas, errores = [], []
    with open(ruta_csv, newline="", encoding="utf-8-sig") as f:
        primera = f.readline()
        f.seek(0)
        delimitador = ";" if (";" in primera and "," not in primera) else ","  # Excel en español usa ;
        for numero, fila in enumerate(csv.DictReader(f, delimiter=delimitador), start=2):
            nss = (fila.get("nss") or "").strip()
            resultado = _normalizar(fila.get("resultado"))
            motivo = (fila.get("motivo") or "").strip()
            if not nss:
                errores.append(f"Renglón {numero}: falta el NSS.")
            elif resultado in _ALTA:
                filas.append({"nss": nss, "estado": almacen.ASEGURADO, "motivo": ""})
            elif resultado in _RECHAZO:
                filas.append({"nss": nss, "estado": almacen.RECHAZADO, "motivo": motivo or "Sin motivo indicado"})
            else:
                errores.append(f"Renglón {numero}: resultado desconocido «{fila.get('resultado')}».")
    return filas, errores
