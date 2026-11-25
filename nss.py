# =============================================================================
# nss.py · Lee y valida el Número de Seguridad Social (NSS)
#
# Este archivo NO usa Telegram. Solo hace tres cosas:
#   1. Saca el NSS de un PDF (o de un texto).
#   2. Revisa que tenga el formato correcto (11 dígitos).
#   3. Revisa el último dígito (dígito verificador) para detectar errores de
#      captura, por ejemplo un número cambiado.
# Está separado de bot.py para poder probarlo solo, sin internet.
# =============================================================================
import re

import pdfplumber

LARGO_NSS = 11

# Busca "Seguridad Social" y, después de esa etiqueta, 11 dígitos
# (permite espacios o guiones entre los dígitos). (?!\d) evita leer un número más largo.
_CON_ETIQUETA = re.compile(r"seguridad\s+social\D{0,25}?((?:\d[ \-]?){11})(?!\d)", re.IGNORECASE)
# Plan B: una sola secuencia de exactamente 11 dígitos en todo el documento.
_SUELTO = re.compile(r"(?<!\d)(\d{11})(?!\d)")


def solo_digitos(texto: str) -> str:
    """'1234 5678-903' -> '12345678903'."""
    return re.sub(r"\D", "", texto)


def enmascarar(nss: str) -> str:
    """'12345678903' -> '*******8903'. Se usa en mensajes al personal y en la terminal,
    para no mostrar el NSS completo donde no hace falta."""
    return "*" * max(len(nss) - 4, 0) + nss[-4:]


def calcular_digito_verificador(primeros_10: str) -> int:
    """Calcula el último dígito del NSS con un algoritmo tipo Luhn.

    Cada dígito se multiplica por 1 o por 2 (alternando, empezando con 1).
    Si el producto tiene dos cifras, se suman esas cifras (14 -> 1 + 4).
    El dígito verificador es lo que falta para llegar al siguiente múltiplo de 10.
    NOTA: es la regla que se usa comúnmente para validar el NSS; se puede apagar
    en config.json ("validar_digito_verificador": false) si el área indica otra cosa."""
    suma = 0
    for posicion, caracter in enumerate(primeros_10):
        producto = int(caracter) * (1 if posicion % 2 == 0 else 2)
        suma += producto // 10 + producto % 10
    return (10 - suma % 10) % 10


def validar_nss(nss: str, exigir_digito_verificador: bool = True) -> tuple[bool, str]:
    """Devuelve (es_valido, motivo). Si es válido, el motivo viene vacío."""
    if not nss.isdigit() or len(nss) != LARGO_NSS:
        return False, f"El NSS debe tener exactamente {LARGO_NSS} dígitos y solo números."
    if exigir_digito_verificador and calcular_digito_verificador(nss[:-1]) != int(nss[-1]):
        return False, "El último dígito no coincide: puede haber un error de captura."
    return True, ""


def extraer_nss_de_texto(texto: str):
    """Devuelve el NSS encontrado en el texto, o None si no hay uno claro."""
    encontrado = _CON_ETIQUETA.search(texto)
    if encontrado:
        return solo_digitos(encontrado.group(1))
    candidatos = set(_SUELTO.findall(texto))
    if len(candidatos) == 1:  # si hay dos o más números de 11 dígitos, es ambiguo
        return candidatos.pop()
    return None


def leer_pdf(ruta) -> tuple:
    """Lee un PDF y devuelve (nss, motivo).
    motivo: 'ok', 'pdf_invalido', 'sin_texto' (PDF escaneado o foto) o 'no_encontrado'."""
    try:
        with pdfplumber.open(ruta) as pdf:
            texto = "\n".join((pagina.extract_text() or "") for pagina in pdf.pages[:3])
    except Exception:
        return None, "pdf_invalido"
    if not texto.strip():
        return None, "sin_texto"
    nss = extraer_nss_de_texto(texto)
    return (nss, "ok") if nss else (None, "no_encontrado")
