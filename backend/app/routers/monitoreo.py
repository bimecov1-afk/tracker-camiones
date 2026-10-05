from datetime import date, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query

from ..auth import requiere
from ..config import LIMA, get_settings, hoy_lima
from ..db import get_db
from ..hojas import agrupar, armar_hoja, filas_hoja
from ..services.callmebot import avisar

router = APIRouter(tags=["monitoreo"])


def _ultimo_punto(placa: str, fecha: str, vuelta: int) -> dict | None:
    r = (get_db().from_("ubicaciones").select("ts,lat,lon,bateria")
         .eq("placa", placa).eq("fecha", fecha).eq("vuelta", vuelta)
         .order("ts", desc=True).limit(1).execute().data)
    return r[0] if r else None


@router.get("/monitoreo/camiones")
def camiones(fecha: date | None = Query(None, description="Por defecto hoy (Lima)"),
             _=Depends(requiere("monitoreo"))):
    """Todas las hojas del día con su último punto GPS y sus paradas (para el mapa)."""
    f = str(fecha or hoy_lima())
    filas = get_db().from_("asignaciones").select("*").eq("fecha", f).execute().data
    out = []
    for (placa, fe, vuelta), v in sorted(agrupar(filas).items()):
        h = armar_hoja(v)
        h["ultimo_punto"] = _ultimo_punto(placa, fe, vuelta) if h["estado"] != "asignada" else None
        out.append(h)
    return out


@router.get("/hojas-ruta/{placa}/{fecha}/{vuelta}/recorrido")
def recorrido(placa: str, fecha: date, vuelta: int, _=Depends(requiere("monitoreo"))):
    placa = placa.upper()
    filas = filas_hoja(placa, fecha, vuelta)
    if not filas:
        raise HTTPException(404, "Hoja no encontrada")
    puntos = (get_db().from_("ubicaciones").select("ts,lat,lon,bateria")
              .eq("placa", placa).eq("fecha", str(fecha)).eq("vuelta", vuelta)
              .order("ts").limit(2000).execute().data)
    return {**armar_hoja(filas), "puntos": puntos}


# --- tarea periódica: "sin reporte de GPS" -------------------------------------
_avisados: dict[tuple, str] = {}  # hoja → ts del último punto ya avisado (en memoria; basta para la demo)


@router.post("/tareas/revisar-gps", tags=["tareas"],
             summary="Llamar cada 5-10 min desde un cron externo (cron-job.org, UptimeRobot…)")
def revisar_gps(bg: BackgroundTasks, x_cron_key: str = Header(...)):
    s = get_settings()
    if not s.cron_key or x_cron_key != s.cron_key:
        raise HTTPException(401, "Clave de cron inválida")
    hoy = str(hoy_lima())
    filas = (get_db().from_("asignaciones").select("*").eq("fecha", hoy)
             .not_.is_("inicio_ts", "null").is_("fin_ts", "null").execute().data)
    limite = datetime.now(LIMA) - timedelta(minutes=s.sin_gps_min)
    alertas = []
    for (placa, fe, vuelta), v in agrupar(filas).items():
        p = _ultimo_punto(placa, fe, vuelta)
        ref = p["ts"] if p else v[0]["inicio_ts"]
        if datetime.fromisoformat(ref) < limite and _avisados.get((placa, fe, vuelta)) != ref:
            _avisados[(placa, fe, vuelta)] = ref
            alertas.append(placa)
            hora = datetime.fromisoformat(ref).astimezone(LIMA).strftime("%H:%M")
            bg.add_task(avisar, "sin_gps",
                        f"📡 {placa} (vuelta {vuelta}) sin reporte de GPS desde las {hora}.")
    return {"revisadas": len(agrupar(filas)), "alertas": alertas}
