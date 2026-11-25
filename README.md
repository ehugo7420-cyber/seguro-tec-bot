# SeguroTec · Bot de Telegram para entregar el NSS del seguro facultativo del IMSS

**Alumno:** Espinosa Pérez José Hugo
**Materia:** Fundamentos de Ingeniería de Software (SCC-1007)
**Empresa:** SeguroTec


**Enlace del bot:** https://t.me/MiSeguroTec_bot (solo responde cuando lo tengo encendido en mi computadora)

## 1. El problema

**¿Cómo se entrega el NSS hoy?**
Para tener su NSS, el alumno lo saca en línea en el portal del IMSS o en persona, haciendo fila en una sucursal. Después lo tiene que entregar en Servicios Escolares.

**¿Qué falla?**
En las sucursales fallan la espera y la falta de personal. En línea puede tardar en cargar la página o el alumno puede equivocarse al escribir los datos que le piden.

**¿Qué consecuencias tiene para el alumno?**
- Puede no tener su NSS cuando la escuela se lo pide.
- Por la falta de personal no lo atienden rápido, o no logra sacarlo en línea.
- No sabe si Servicios Escolares ya tiene su NSS ni si ya está dado de alta.
  

## 2. Qué hace el bot (la solución)

**Lo que hace el alumno:**
1. Toca **Subir mi NSS** en el bot y escribe su número de control y su carrera.
2. Sube el PDF de su constancia o escribe su NSS en el chat.
3. El bot lee el NSS y lo valida (11 dígitos y el último dígito).
4. El alumno confirma que el NSS es correcto y queda **pendiente**.
5. Cuando el personal carga el resultado, el bot le avisa si ya está dado de alta o por qué lo rechazaron.
6. Con el botón **Mi estado** puede consultar en qué va, sin hacer fila.

**Lo que hace el personal** (solo los ID de `ADMIN_IDS`):
- `/lote` genera un archivo .csv con los alumnos que ya entregaron su NSS y están pendientes, con su número de control y su NSS.
- `/acuse_demo` lee un acuse de ejemplo y marca a cada alumno como asegurado o rechazado. A cada alumno le llega un aviso con el resultado y, si lo rechazaron, el motivo. El personal recibe un resumen con los totales.
- `/tablero` muestra cuántos alumnos le escribieron al bot, cuántos no han entregado su NSS, cuántos están asegurados, rechazados o en trámite, y los totales por carrera.
- `/recordar` manda los recordatorios en ese momento.

**Recordatorio automático:** el bot manda un recordatorio a los alumnos que le escribieron pero no han entregado su NSS.

## 3. Qué automatiza y qué sigue siendo humano

| Lo hace el bot | Lo sigue haciendo una persona |
| --- | --- |
| Pedir y recibir el NSS | Cargar el lote en la plataforma del IMSS |
| Leer el PDF y validar el formato | Revisar los casos raros (PDF ilegible o rechazos poco comunes) |
| Armar el archivo de altas | Confirmar el formato real del lote con Servicios Escolares |
| Avisar al alumno el resultado | |
| Recordar a quien no ha entregado | |
| Contar asegurados, rechazados y pendientes | |

Con esto se reducen las filas en Servicios Escolares y el alumno puede consultar su estado sin ir a preguntar.

**El bot nunca se conecta al IMSS.** Cargar el lote en la plataforma lo hace el personal autorizado.

## 4. Cómo probarlo

Pasos mínimos:

1. Instalar las librerías:
   ```
   python -m pip install -r requirements.txt
   ```
2. Crear el archivo `.env` con el token del bot (puedes copiar `.env.ejemplo`). El `.env` no se sube a GitHub.
3. Encender el bot:
   ```
   python bot.py
   ```
4. Abrir el bot en Telegram y escribir `/start`.

Para probar sin datos reales hay constancias inventadas en la carpeta `datos_prueba/`. Los pasos completos están en `GUIA.md`.

## 5. Resultados

Estos son los resultados reales de las pruebas que hice en noviembre de 2026:

- **Pruebas automáticas de los módulos:** 27 pruebas a `nss.py`, `almacen.py` y `lote.py`. Las 27 pasaron.
- **Pruebas automáticas del flujo del bot:** 7 pruebas con chats simulados (el recorrido del alumno, el lote, el acuse y los recordatorios). Las 7 pasaron.
- La evidencia está en `pruebas/resultado_pruebas.txt`.
- **Pruebas a mano en Telegram** con constancias inventadas:
  - Constancia válida: el bot lee el NSS y pide confirmarlo.
  - Constancia con el último dígito mal: el bot la rechaza y explica por qué.
  - Constancia sin NSS: el bot dice que no encontró uno claro.
  - Constancia escaneada: el bot pide escribir el NSS en el chat.
  - Con tres alumnos de prueba, `/lote` generó el archivo .csv, `/acuse_demo` marcó a dos como asegurados y a uno como rechazado, y `/tablero` mostró los totales correctos.

**Todavía no medí** el tiempo que se ahorra, no hice encuestas a compañeros ni una prueba de usabilidad con usuarios. Por eso no pongo cifras de esas cosas.

## 6. Contenido del repositorio

- `bot.py`: es el programa principal. Atiende los botones, los mensajes y los comandos del personal en Telegram.
- `nss.py`: lee el NSS de un PDF y lo valida (11 dígitos y el último dígito).
- `almacen.py`: guarda en una base de datos SQLite quién entregó su NSS y en qué estado va.
- `lote.py`: arma el archivo .csv de altas y lee el acuse de ejemplo.
- `config.json`: textos y reglas que se pueden cambiar sin programar, como las carreras y la hora del recordatorio.
- `.env.ejemplo`: muestra cómo se escribe el archivo `.env`, donde van el token del bot y los ID del personal. El `.env` real no se sube a GitHub.
- `requirements.txt`: lista de las librerías que hay que instalar.
- `generar_constancias.py` y `datos_prueba/`: constancias y un acuse inventados para probar el bot.
- `pruebas/`: las pruebas automáticas y su resultado.
- `evidencias/`: carpeta para las mediciones reales, que todavía están pendientes.
- `GUIA.md` y `EXPLICACIÓN.md`: cómo instalar el bot y cómo funciona cada parte.
- `probar.bat` e `iniciar_bot.bat`: atajos para Windows para correr las pruebas y encender el bot.

## 7. Limitaciones

- El bot solo puede leer PDF que tengan texto. Si el alumno manda una foto o un PDF escaneado, tiene que escribir su NSS en el chat.
- El bot revisa que el NSS tenga el formato correcto y que el alumno lo confirme, pero no puede saber si ese NSS es realmente de esa persona. Eso lo valida el IMSS.
- El bot solo puede avisarle a los alumnos que ya le escribieron.
- El bot solo funciona mientras `python bot.py` esté corriendo en la computadora. Para usarlo siempre haría falta ponerlo en un servidor.
- El formato del lote y del acuse son de ejemplo. Servicios Escolares tendría que confirmar el formato real.
- Todo se probó con datos inventados y el bot no se conecta al IMSS. Para usarlo con alumnos reales haría falta autorización del área y revisar el aviso de privacidad.
