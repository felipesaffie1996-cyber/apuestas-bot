"""
=============================================================
APUESTAS BOT — Registro de apuestas en vivo con IA
=============================================================
Bot de Telegram que:
1. Responde preguntas en lenguaje natural sobre partidos en vivo
2. Registra apuestas a gol adicional
3. Monitorea resultados automáticamente
4. Lleva historial de aciertos/desaciertos
=============================================================
"""

import os
import json
import time
import requests
import threading
from datetime import datetime

# ============================================================
# CONFIGURACIÓN
# ============================================================
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "8828287594:AAHQwMud1Oaimp-yyKj8OjRHdikbRHOYHXU")
TELEGRAM_CHAT_ID = os.environ.get("APUESTAS_CHAT_ID", "1491964944")
API_KEY          = os.environ.get("API_FOOTBALL_KEY", "7aa252fd9c63236a40e473bb6d518319")
ANTHROPIC_KEY    = os.environ.get("ANTHROPIC_API_KEY", "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")

LIGAS = {
    39:  "Premier League 🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    78:  "Bundesliga 🇩🇪",
    71:  "Brasileirao 🇧🇷",
    61:  "Ligue 1 🇫🇷",
    135: "Serie A 🇮🇹",
    203: "Süper Lig 🇹🇷",
    144: "Pro League 🇧🇪",
    140: "La Liga 🇪🇸",
    262: "Liga MX 🇲🇽",
    94:  "Primeira Liga 🇵🇹",
    265: "Primera División ARG 🇦🇷",
    347: "Primera División CHI 🇨🇱",
    242: "Liga 1 Perú 🇵🇪",
    239: "Apertura Paraguay 🇵🇾",
    268: "Liga Pro Ecuador 🇪🇨",
    278: "Primera División Uruguay 🇺🇾",
    253: "MLS 🇺🇸",
}

APUESTAS_FILE  = "apuestas.json"
HISTORIAL_FILE = "historial.json"

# ============================================================
# STORAGE
# ============================================================
def cargar_apuestas():
    try:
        with open(APUESTAS_FILE) as f:
            return json.load(f)
    except:
        return {}

def guardar_apuestas(data):
    with open(APUESTAS_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def cargar_historial():
    try:
        with open(HISTORIAL_FILE) as f:
            return json.load(f)
    except:
        return []

def guardar_historial(data):
    with open(HISTORIAL_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ============================================================
# API FOOTBALL
# ============================================================
def api_get(endpoint, params={}):
    headers = {"x-apisports-key": API_KEY}
    try:
        r = requests.get(
            f"https://v3.football.api-sports.io/{endpoint}",
            headers=headers,
            params=params,
            timeout=10
        )
        return r.json().get("response", [])
    except:
        return []

def obtener_partidos_vivos():
    """Retorna partidos en vivo — incluye todas las ligas."""
    return api_get("fixtures", {"live": "all"})

def obtener_todos_partidos_vivos():
    """Retorna TODOS los partidos en vivo sin filtro."""
    return api_get("fixtures", {"live": "all"})

def obtener_partido_por_id(fixture_id):
    data = api_get("fixtures", {"id": fixture_id})
    return data[0] if data else None

# ============================================================
# TELEGRAM
# ============================================================
def enviar_mensaje(texto, chat_id=None):
    cid = chat_id or TELEGRAM_CHAT_ID
    if not cid:
        return
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": cid, "text": texto, "parse_mode": "HTML"},
        timeout=10
    )

def get_updates(offset=0):
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={"offset": offset, "timeout": 30},
            timeout=35
        )
        return r.json().get("result", [])
    except:
        return []

# ============================================================
# FORMATEO DE PARTIDOS
# ============================================================
def formatear_partidos(partidos):
    if not partidos:
        return "No hay partidos en vivo ahora mismo en las ligas monitoreadas."

    texto = "⚽ <b>Partidos en vivo:</b>\n\n"
    for p in partidos:
        liga   = LIGAS.get(p["league"]["id"], f"{p['league']['name']} ({p['league']['country']})")
        local  = p["teams"]["home"]["name"]
        visita = p["teams"]["away"]["name"]
        gl     = p["goals"]["home"] or 0
        gv     = p["goals"]["away"] or 0
        minuto = p["fixture"]["status"].get("elapsed", "?")
        fid    = p["fixture"]["id"]

        texto += f"🏟 <b>{local} {gl}-{gv} {visita}</b>\n"
        texto += f"   {liga} | Min {minuto}' | ID: {fid}\n\n"

    return texto

def formatear_partidos_min80(partidos):
    filtrados = [
        p for p in partidos
        if (p["fixture"]["status"].get("elapsed") or 0) >= 80
    ]
    if not filtrados:
        return "No hay partidos en minuto 80 o superior ahora mismo."
    return formatear_partidos(filtrados)

# ============================================================
# REGISTRO DE APUESTAS
# ============================================================
def registrar_apuesta(fixture_id, partido_info, chat_id):
    apuestas = cargar_apuestas()
    fid_str = str(fixture_id)

    if fid_str in apuestas:
        return f"Ya tienes una apuesta registrada para ese partido."

    goles_actual = (partido_info["goals"]["home"] or 0) + (partido_info["goals"]["away"] or 0)
    minuto = partido_info["fixture"]["status"].get("elapsed", "?")
    local  = partido_info["teams"]["home"]["name"]
    visita = partido_info["teams"]["away"]["name"]
    gl     = partido_info["goals"]["home"] or 0
    gv     = partido_info["goals"]["away"] or 0

    apuestas[fid_str] = {
        "fixture_id":     fixture_id,
        "local":          local,
        "visita":         visita,
        "marcador_apuesta": f"{gl}-{gv}",
        "goles_al_apostar": goles_actual,
        "minuto_apuesta": minuto,
        "timestamp":      datetime.now().isoformat(),
        "chat_id":        chat_id,
        "resultado":      None
    }
    guardar_apuestas(apuestas)

    return (
        f"✅ <b>Apuesta registrada</b>\n\n"
        f"⚽ {local} {gl}-{gv} {visita}\n"
        f"⏱ Minuto: {minuto}'\n"
        f"🎯 Apostando a: gol adicional\n"
        f"📊 Goles actuales: {goles_actual}\n\n"
        f"Te avisaré cuando termine el partido."
    )

def mostrar_historial():
    historial = cargar_historial()
    if not historial:
        return "No tienes apuestas registradas aún."

    aciertos = sum(1 for h in historial if h["resultado"] == "ACIERTO")
    total    = len(historial)
    tasa     = round(aciertos / total * 100) if total > 0 else 0

    texto = f"📊 <b>Tu historial de apuestas</b>\n"
    texto += f"✅ Aciertos: {aciertos}/{total} ({tasa}%)\n\n"

    for h in historial[-10:]:  # últimas 10
        emoji = "✅" if h["resultado"] == "ACIERTO" else "❌"
        texto += f"{emoji} {h['local']} vs {h['visita']}\n"
        texto += f"   Min {h['minuto_apuesta']}' | {h['marcador_apuesta']} → {h.get('marcador_final', '?')}\n\n"

    return texto

# ============================================================
# MONITOR DE APUESTAS PENDIENTES
# ============================================================
def monitor_apuestas():
    """Hilo que monitorea partidos apostados y notifica resultado."""
    while True:
        try:
            apuestas = cargar_apuestas()
            historial = cargar_historial()
            pendientes = {k: v for k, v in apuestas.items() if v["resultado"] is None}

            for fid_str, apuesta in pendientes.items():
                partido = obtener_partido_por_id(int(fid_str))
                if not partido:
                    continue

                status = partido["fixture"]["status"]["short"]
                if status not in ["FT", "AET", "PEN"]:
                    continue

                # Partido terminado — calcular resultado
                gl_final = partido["goals"]["home"] or 0
                gv_final = partido["goals"]["away"] or 0
                goles_final = gl_final + gv_final
                goles_apuesta = apuesta["goles_al_apostar"]

                resultado = "ACIERTO" if goles_final > goles_apuesta else "FALLO"
                marcador_final = f"{gl_final}-{gv_final}"

                # Actualizar apuesta
                apuestas[fid_str]["resultado"] = resultado
                apuestas[fid_str]["marcador_final"] = marcador_final
                guardar_apuestas(apuestas)

                # Agregar al historial
                registro = {**apuesta, "resultado": resultado, "marcador_final": marcador_final}
                historial.append(registro)
                guardar_historial(historial)

                # Notificar
                emoji = "✅" if resultado == "ACIERTO" else "❌"
                msg = (
                    f"{emoji} <b>Resultado de tu apuesta</b>\n\n"
                    f"⚽ {apuesta['local']} {marcador_final} {apuesta['visita']}\n"
                    f"🎯 Apostaste en min {apuesta['minuto_apuesta']}' ({apuesta['marcador_apuesta']})\n"
                    f"📊 Goles al apostar: {goles_apuesta} → Final: {goles_final}\n\n"
                    f"<b>{resultado}</b> {'🎉' if resultado == 'ACIERTO' else '😔'}"
                )
                enviar_mensaje(msg, apuesta["chat_id"])

        except Exception as e:
            print(f"[MONITOR ERROR] {e}")

        time.sleep(60)

# ============================================================
# IA — PROCESAR MENSAJE CON CLAUDE
# ============================================================
def procesar_mensaje(mensaje, partidos_vivos):
    """Detecta la intención del mensaje con palabras clave."""
    msg = mensaje.lower().strip()

    # Detectar apuesta
    palabras_apuesta = ["apuest", "aposto", "me juego", "pongo a", "registro apuesta"]
    if any(p in msg for p in palabras_apuesta):
        # Buscar partido mencionado
        for p in partidos_vivos:
            local  = p["teams"]["home"]["name"].lower()
            visita = p["teams"]["away"]["name"].lower()
            if local in msg or visita in msg:
                return {"accion": "apostar", "fixture_id": p["fixture"]["id"], "respuesta": ""}
        return {"accion": "apostar_sin_partido", "fixture_id": None, "respuesta": ""}

    # Detectar historial
    if any(p in msg for p in ["historial", "mis apuestas", "cuantos aciertos", "estadistica", "resultado"]):
        return {"accion": "historial", "fixture_id": None, "respuesta": ""}

    # Detectar minuto 80+
    if any(p in msg for p in ["80", "minuto 8", "urgente", "ultimo", "final", "cierre"]):
        return {"accion": "listar_80", "fixture_id": None, "respuesta": ""}

    # Por defecto listar todos
    return {"accion": "listar", "fixture_id": None, "respuesta": ""}

# ============================================================
# MAIN LOOP
# ============================================================
def main():
    print("=" * 50)
    print("⚽ APUESTAS BOT — Iniciado")
    print("=" * 50)

    if not ANTHROPIC_KEY:
        print("❌ ERROR: Falta ANTHROPIC_API_KEY en variables de entorno")
        return

    if not TELEGRAM_CHAT_ID:
        print("⚠️  APUESTAS_CHAT_ID no configurado — el bot responderá a cualquier chat")

    # Iniciar monitor de apuestas en hilo separado
    t = threading.Thread(target=monitor_apuestas, daemon=True)
    t.start()

    offset = 0
    print("✅ Escuchando mensajes...")

    while True:
        updates = get_updates(offset)

        for update in updates:
            offset = update["update_id"] + 1
            msg = update.get("message", {})
            texto = msg.get("text", "").strip()
            chat_id = str(msg.get("chat", {}).get("id", ""))

            if not texto or not chat_id:
                continue

            print(f"[MSG] {chat_id}: {texto}")

            # Obtener partidos en vivo
            partidos = obtener_partidos_vivos()

            # Comando debug — ver todos los partidos sin filtro
            if "debug" in texto.lower() or "todos los partidos" in texto.lower():
                todos = obtener_todos_partidos_vivos()
                if not todos:
                    enviar_mensaje("No hay partidos en vivo ahora mismo.", chat_id)
                else:
                    msg = f"🔍 <b>Todos los partidos en vivo ({len(todos)}):</b>\n\n"
                    for p in todos[:20]:
                        lid = p["league"]["id"]
                        nombre = p["league"]["name"]
                        local = p["teams"]["home"]["name"]
                        visita = p["teams"]["away"]["name"]
                        min_actual = p["fixture"]["status"].get("elapsed", "?")
                        msg += f"ID Liga: <b>{lid}</b> — {nombre}\n{local} vs {visita} | Min {min_actual}'\n\n"
                    enviar_mensaje(msg, chat_id)
                continue

            # Procesar mensaje
            resultado = procesar_mensaje(texto, partidos)
            accion    = resultado.get("accion")
            fixture_id = resultado.get("fixture_id")
            respuesta  = resultado.get("respuesta", "")

            if accion == "listar":
                enviar_mensaje(formatear_partidos(partidos), chat_id)

            elif accion == "listar_80":
                enviar_mensaje(formatear_partidos_min80(partidos), chat_id)

            elif accion == "apostar_sin_partido":
                enviar_mensaje("¿A qué partido quieres apostar? Dime el nombre del equipo.", chat_id)

            elif accion == "apostar" and fixture_id:
                partido = obtener_partido_por_id(fixture_id)
                if partido:
                    msg_apuesta = registrar_apuesta(fixture_id, partido, chat_id)
                    enviar_mensaje(msg_apuesta, chat_id)
                else:
                    enviar_mensaje("No encontré ese partido. ¿Puedes especificar mejor?", chat_id)

            elif accion == "historial":
                enviar_mensaje(mostrar_historial(), chat_id)

            else:
                if respuesta:
                    enviar_mensaje(respuesta, chat_id)

        time.sleep(1)

if __name__ == "__main__":
    main()
