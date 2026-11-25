# =============================================================================
# generar_constancias.py · Crea constancias y un acuse de PRUEBA con datos INVENTADOS
#
# Sirve para probar el bot sin usar documentos reales de nadie.
# Genera en datos_prueba/:
#   constancias/constancia_prueba_1.pdf ... _3.pdf  -> NSS válidos
#   constancias/constancia_nss_con_error.pdf        -> último dígito mal (el bot lo rechaza)
#   constancias/constancia_sin_nss.pdf              -> no trae NSS
#   constancias/constancia_escaneada.pdf            -> solo imagen, sin texto (el bot no la puede leer)
#   acuse_simulado.csv                              -> resultado inventado del "IMSS"
#   LEEME.txt                                       -> qué NSS tiene cada archivo
# Se ejecuta con:  python generar_constancias.py
# =============================================================================
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from nss import calcular_digito_verificador

CARPETA = Path(__file__).parent / "datos_prueba"
CONSTANCIAS = CARPETA / "constancias"

# Los 10 primeros dígitos son inventados; el último se calcula para que el NSS sea "válido".
BASES = ["1234567890", "2345678901", "3456789012"]
VALIDOS = [base + str(calcular_digito_verificador(base)) for base in BASES]
CON_ERROR = BASES[0] + str((calcular_digito_verificador(BASES[0]) + 1) % 10)  # dígito final equivocado


def dibujar(ruta, nss, nombre):
    c = canvas.Canvas(str(ruta), pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(72, 720, "CONSTANCIA DE PRUEBA (NO ES UN DOCUMENTO REAL)")
    c.setFont("Helvetica", 11)
    c.drawString(72, 690, f"Nombre: {nombre}")
    if nss:
        c.drawString(72, 670, f"Número de Seguridad Social (NSS): {nss}")
    c.drawString(72, 650, "Documento inventado para probar el prototipo SeguroTec.")
    c.save()


def dibujar_escaneada(ruta):
    """PDF que solo contiene una imagen (sin texto), como una foto o un escaneo."""
    from PIL import Image, ImageDraw
    imagen = Image.new("RGB", (800, 400), "white")
    ImageDraw.Draw(imagen).text((40, 60), f"NSS de prueba: {VALIDOS[0]}", fill="black")
    ruta_png = ruta.with_suffix(".png")
    imagen.save(ruta_png)
    c = canvas.Canvas(str(ruta), pagesize=letter)
    c.drawImage(str(ruta_png), 72, 400, width=400, height=200)
    c.save()
    ruta_png.unlink()


def main():
    CONSTANCIAS.mkdir(parents=True, exist_ok=True)
    for i, nss in enumerate(VALIDOS, start=1):
        dibujar(CONSTANCIAS / f"constancia_prueba_{i}.pdf", nss, f"ALUMNO DE PRUEBA {i}")
    dibujar(CONSTANCIAS / "constancia_nss_con_error.pdf", CON_ERROR, "ALUMNO DE PRUEBA 4")
    dibujar(CONSTANCIAS / "constancia_sin_nss.pdf", None, "ALUMNO DE PRUEBA 5")
    dibujar_escaneada(CONSTANCIAS / "constancia_escaneada.pdf")

    with open(CARPETA / "acuse_simulado.csv", "w", encoding="utf-8", newline="") as f:
        f.write("nss,resultado,motivo\n")
        f.write(f"{VALIDOS[0]},alta,\n")
        f.write(f"{VALIDOS[1]},alta,\n")
        f.write(f"{VALIDOS[2]},rechazada,Datos del NSS no coinciden con la CURP (motivo inventado)\n")

    with open(CARPETA / "LEEME.txt", "w", encoding="utf-8") as f:
        f.write("DATOS DE PRUEBA INVENTADOS. Nunca uses constancias reales de nadie.\n\n")
        for i, nss in enumerate(VALIDOS, start=1):
            f.write(f"constancia_prueba_{i}.pdf        NSS {nss}  (válido)\n")
        f.write(f"constancia_nss_con_error.pdf    NSS {CON_ERROR}  (último dígito mal: el bot lo rechaza)\n")
        f.write("constancia_sin_nss.pdf          sin NSS (el bot no encuentra nada)\n")
        f.write("constancia_escaneada.pdf        solo imagen (el bot pide escribir el NSS)\n\n")
        f.write("acuse_simulado.csv: el NSS 1 y el NSS 2 salen como alta; el NSS 3 sale rechazado.\n")
        f.write("Números de control de ejemplo para probar: 21010001, 21010002, 21010003 (inventados).\n")
    print("Listo: revisa la carpeta datos_prueba/")


if __name__ == "__main__":
    main()
