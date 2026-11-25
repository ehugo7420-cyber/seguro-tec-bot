# Guía para instalar y encender el bot

## 1. Instalar lo necesario
1. Instala **Python 3.11 o superior** desde python.org. En el instalador marca **«Add Python to PATH»**.
2. Abre una terminal dentro de esta carpeta (en el explorador: clic en la barra de dirección, escribe `cmd` y Enter).
3. Ejecuta: `python -m pip install -r requirements.txt`

## 2. Crear tu bot en Telegram
1. En Telegram busca **@BotFather** y escríbele `/newbot`.
2. Ponle un nombre (por ejemplo, «SeguroTec») y un usuario que termine en `bot`.
3. BotFather te da un **token** (una cadena larga). No lo compartas con nadie ni lo subas a GitHub.

## 3. Configurar el token
1. Copia `.env.ejemplo` y renombra la copia a `.env`.
2. Pega tu token en la línea `TELEGRAM_TOKEN=`.

## 4. Encenderlo
- Ejecuta `python bot.py` o haz doble clic en `iniciar_bot.bat` (este se reinicia solo si se detiene).
- Abre tu bot en Telegram y escribe `/start`.
- Para apagarlo: `Ctrl + C` en la terminal.

## 5. Activar los comandos del personal
1. Con el bot encendido, escríbele `/miid` y copia el número que te da.
2. Pégalo en `ADMIN_IDS=` del archivo `.env`.
3. Apaga el bot (`Ctrl + C`) y enciéndelo otra vez.

## 6. Probarlo sin datos reales
Los archivos para probar están en `datos_prueba/` (lee `LEEME.txt`). **Todo es inventado; no uses tu NSS real ni constancias de nadie.**
1. `/start` → **Subir mi NSS** → número de control `21010001` → carrera → manda `datos_prueba/constancias/constancia_prueba_1.pdf` → **Sí, es correcto**.
2. Repite con `21010002` y la constancia 2, y con `21010003` y la constancia 3 (puedes usar el mismo chat).
3. Como personal: `/lote` (te manda el CSV) → `/acuse_demo` (el bot avisa a cada alumno) → `/tablero`.
4. Como alumno: **Mi estado**. Verás asegurado, asegurado y rechazado con su motivo.
5. Prueba también `constancia_nss_con_error.pdf`, `constancia_sin_nss.pdf` y `constancia_escaneada.pdf` para ver los mensajes de error.

## 7. Correr las pruebas automáticas
Doble clic en `probar.bat` (o `python pruebas/pruebas_seguro.py`). No necesitan token ni internet.

## Problemas comunes
- **«Falta el token»**: el archivo se llama `.env` (no `.env.ejemplo`) y la línea es `TELEGRAM_TOKEN=...` sin espacios.
- **`python` no se reconoce**: reinstala Python y marca «Add Python to PATH».
- **Error de `job_queue`**: instala con `python -m pip install -r requirements.txt` (trae `python-telegram-bot[job-queue]`).
- **El bot no responde**: revisa que la terminal siga abierta; solo responde mientras tu computadora lo tiene encendido.
