"""Avisos por WhatsApp con CallMeBot.

Se llama desde BackgroundTasks: nunca bloquea ni hace fallar la operación.
Cada destinatario activa su propio apikey (la API gratuita solo envía
al número que la activó).
"""
import logging
import time

import httpx

from ..config import get_settings

log = logging.getLogger("callmebot")
URL = "https://api.callmebot.com/whatsapp.php"


def avisar(evento: str, texto: str) -> None:
    s = get_settings()
    if evento not in s.eventos_aviso:
        return
    log.info("Aviso %s: %s", evento, texto)
    for telefono, apikey in s.destinatarios:
        for intento in range(3):
            try:
                r = httpx.get(URL, params={"phone": telefono, "text": texto, "apikey": apikey}, timeout=20)
                if r.status_code == 200:
                    log.info("WhatsApp %s → %s OK", evento, telefono[-4:])
                    break
                log.warning("WhatsApp %s → %s HTTP %s", evento, telefono[-4:], r.status_code)
            except httpx.HTTPError as e:
                log.warning("WhatsApp %s → %s error %s", evento, telefono[-4:], e)
            time.sleep(2 * (intento + 1))
