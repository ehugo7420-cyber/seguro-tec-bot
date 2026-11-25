# Explicación del proyecto (para estudiarla antes de presentarlo)

> Léelo completo una vez y luego abre cada archivo mientras repasas. Si puedes explicar la sección 3 con tus palabras, ya dominas el proyecto.

## 1. La idea en 30 segundos
Todos los alumnos inscritos en una institución pública tienen derecho al seguro facultativo del IMSS, pero para darlos de alta tienen que obtener su **NSS** (número de seguridad social) y entregarlo en Servicios Escolares. Hoy se entrega en papel o por correo, se captura a mano, y el alumno normalmente no sabe si ya quedó asegurado.

Mi prototipo es un **bot de Telegram**: el alumno manda su constancia, el bot **lee y valida el NSS**, lo guarda, le **avisa el resultado** y **recuerda** a quien no ha entregado. El personal de Servicios Escolares solo **carga un lote** en la plataforma del IMSS (paso humano) y el bot hace el resto. La jefatura ve un **tablero** con los totales.

## 2. Qué automatiza y qué NO
| Automatiza el bot | Sigue siendo humano |
| --- | --- |
| Pedir y recibir el NSS | Cargar el lote en la plataforma del IMSS (es un sistema externo con credenciales del Tec) |
| Leer el PDF y validar el formato | Revisar los casos raros (PDF ilegible, rechazos poco comunes) |
| Armar el lote de altas | Confirmar con el área el formato real del lote |
| Avisar al alumno el resultado | |
| Recordar a quien no ha entregado | |
| Contar asegurados, rechazados y pendientes por carrera | |

**El bot nunca se conecta al IMSS.** El acuse con el resultado es un archivo de ejemplo, y todos los datos del prototipo son inventados.

## 3. Cómo viaja un NSS (explícalo en este orden)
1. El alumno escribe `/start` → `bot.py` lo anota en la tabla **usuarios** (`almacen.py`).
2. Toca **Subir mi NSS** → el bot le pide número de control, carrera y la constancia. Para saber en qué paso va cada persona usa `context.user_data["paso"]` (control → carrera → pdf → confirmar).
3. El alumno manda el PDF → `bot.py` lo descarga a una carpeta temporal → `nss.py` lo lee con **pdfplumber** y busca el NSS → **el PDF se borra siempre**, solo se guarda el NSS confirmado.
4. `nss.py` valida: 11 dígitos y el último dígito (dígito verificador). Si falla, le explica por qué.
5. El bot le muestra lo que leyó y el alumno **confirma** (así un error de lectura no se guarda).
6. `almacen.py` guarda el registro en **SQLite** con estado `pendiente`.
7. El personal escribe `/lote` → `lote.py` crea un CSV con los pendientes y los pasa a `en_lote`.
8. El personal carga ese CSV en el IMSS (**paso humano**, fuera del bot).
9. El personal manda el acuse (`/acuse_demo` o un CSV) → `lote.py` lo lee → `almacen.py` cambia a `asegurado` o `rechazado` con su motivo → el bot **le avisa a cada alumno**.
10. Todos los días a las 9:00 el bot recuerda a quien le escribió y no entregó. `/tablero` muestra los totales.

**Estados:** `pendiente` → `en_lote` → `asegurado` o `rechazado`. Si lo rechazan, el alumno corrige y vuelve a `pendiente`.

## 4. Qué hace cada archivo
| Archivo | Qué hace | Cómo explicarlo |
| --- | --- | --- |
| `bot.py` | Es el cerebro con Telegram: botones, mensajes, pasos del alumno y comandos del personal. | «Aquí está la conversación. Cada función responde a un botón o comando.» |
| `nss.py` | Lee el NSS del PDF y lo valida. No usa Telegram. | «Lo separé para poder probarlo solo, sin internet.» |
| `almacen.py` | Base de datos SQLite: tablas `usuarios` y `registros`, y todas las consultas. | «Guarda quién entregó, en qué estado va y a quién recordar.» |
| `lote.py` | Genera el CSV de altas y lee el acuse del IMSS (simulado). | «Es el puente con el paso humano.» |
| `config.json` | Textos y reglas que el área puede cambiar sin programar (carreras, días del recordatorio, hora, links). | «Si cambia una regla, se edita aquí y el bot lo usa sin reiniciarse.» |
| `.env` / `.env.ejemplo` | El token del bot y los IDs del personal. | «Los secretos van aquí y no se suben a GitHub.» |
| `generar_constancias.py` | Crea PDFs y un acuse de prueba con datos inventados. | «Probé sin usar documentos reales de nadie.» |
| `datos_prueba/` | Las constancias y el acuse inventados y un `LEEME.txt`. | «Cada archivo prueba un caso: válido, con error, sin NSS, escaneado.» |
| `pruebas/` | Pruebas automáticas: 27 de los módulos (P-01 a P-27) y 7 del flujo del bot (F-01 a F-07). | «Se corren con un doble clic y no necesitan internet.» |
| `evidencias/` | Aquí van las mediciones reales, la encuesta y el SUS. | «Solo datos que yo medí.» |
| `GUIA.md` | Cómo instalar y encender el bot. | |
| `requirements.txt`, `.gitignore`, `.bat` | Librerías, archivos que no se suben a GitHub y atajos para Windows. | |

## 5. Decisiones de diseño y por qué
- **Telegram:** el alumno ya lo tiene en el celular, no hay que instalar nada ni crear cuentas.
- **SQLite:** guarda todo en un archivo, sin servidor. Suficiente para un prototipo.
- **Confirmación del alumno:** nadie sabe mejor que él cuál es su NSS; así se evita guardar una lectura equivocada.
- **Dígito verificador:** detecta errores de captura (un dígito cambiado) antes de que el IMSS rechace el alta. Es la regla que se usa comúnmente para validar el NSS; si el área indica otra, se apaga con `"validar_digito_verificador": false` en `config.json`.
- **Borrar el PDF:** el documento es un dato personal; solo se conserva el NSS confirmado.
- **Comandos solo para el personal:** `ADMIN_IDS` en `.env`; un alumno que escriba `/lote` recibe «solo para el personal».
- **Un número de control no se puede sobrescribir desde otra cuenta**, para que nadie pise el registro de otra persona.
- **En los mensajes y la terminal, el NSS se oculta** (`*******8903`).
- **No hay conexión al IMSS:** es un sistema externo con credenciales del Tec; lo correcto es que lo cargue personal autorizado.

## 6. Límites honestos (dilos tú antes de que te pregunten)
- Solo lee **PDF con texto**. Si es foto o escaneo, el bot pide que el alumno **escriba** el NSS. Leer fotos (OCR) sería una mejora futura.
- El bot **no puede confirmar que el NSS sea de esa persona**; lo único que hace es validar el formato y que el alumno lo confirme. El IMSS es quien rechaza si no coincide.
- Solo puede avisarle a quien **ya le escribió** al bot (así funciona Telegram).
- Responde **solo mientras la computadora donde corre esté encendida**. Para uso real habría que ponerlo en un servidor.
- El formato del lote y del acuse son **de ejemplo**; el área debe confirmar los reales.
- Todo se probó con **datos inventados**. Para usarlo con alumnos reales hace falta autorización del área y revisar el aviso de privacidad.

## 7. Preguntas que puede hacer el profe
- **¿Dónde está la automatización?** En `bot.py`/`nss.py`: lee y valida el NSS sin capturarlo a mano, arma el lote, avisa y recuerda.
- **¿Qué pasa si el alumno manda una foto?** `leer_pdf` devuelve `sin_texto` y el bot le pide que escriba el NSS.
- **¿Cómo sabes que el NSS es correcto?** Valido formato y dígito verificador, y el alumno confirma. La validación final la hace el IMSS.
- **¿Qué datos guardas?** Número de control, carrera, NSS, estado y el ID del chat. No guardo el PDF ni el nombre.
- **¿Qué pasa si el IMSS rechaza el alta?** El acuse trae el motivo, el bot se lo manda al alumno y puede corregir su NSS.
- **¿Qué pasa si el bot se apaga?** No recibe mensajes, pero los datos siguen en `seguro.db`; al encenderlo, todo continúa.
- **¿Cómo lo probaste?** Con 27 pruebas de los módulos, 7 del flujo con chats simulados y PDFs de prueba con cinco casos distintos.
- **¿Por qué no usaste Google Forms o Power Automate?** (Responde con tu propia comparación: costo, lectura del NSS en el PDF, protección de datos y qué puedes mantener tú.)
- **¿Qué mejorarías?** OCR para fotos, un servidor para que esté siempre encendido, el formato real del lote y una pantalla para la jefatura.

## 8. Demostración en 3 minutos
1. Muestra el problema (una frase) y el esquema de la sección 3.
2. `/start` → **Subir mi NSS** → sube `constancia_prueba_1.pdf` → confirma.
3. Sube `constancia_nss_con_error.pdf` y muestra cómo lo rechaza y explica por qué.
4. Como personal: `/lote` → muestra el CSV → `/acuse_demo` → muestra el aviso al alumno.
5. `/tablero` y **Mi estado**. Cierra con «qué automatiza, qué no y los límites».
