"""Endpoints de la app Android. El token lleva la placa: el chofer solo ve y toca su hoja."""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..auth import requiere
from ..config import ahora, hoy_lima
from ..db import get_db
from ..hojas import agrupar, armar_hoja, estado_hoja
from ..services.callmebot import avisar

router = APIRouter(prefix="/chofer", tags=["chofer"])
ORD = {1: "1ra", 2: "2da", 3: "3ra", 4: "4ta", 5: "5ta", 6: "6ta", 7: "7ma", 8: "8va", 9: "9na", 10: "10ma"}


def ordinal(n: int) -> str:
    return ORD.get(n, f"{n}°")


def hoja_activa(placa: str) -> list[dict]:
    """Hoja de hoy: la que está en ruta; si no hay, la primera vuelta sin finalizar."""
    filas = (get_db().from_("asignaciones").select("*")
             .eq("placa", placa).eq("fecha", str(hoy_lima())).execute().data)
    hojas = sorted(agrupar(filas).items(), key=lambda kv: kv[0][2])
    abiertas = [v for _, v in hojas if estado_hoja(v) != "finalizada"]
    en_ruta = [v for v in abiertas if estado_hoja(v) == "en_ruta"]
    if en_ruta:
        return en_ruta[0]
    if abiertas:
        return abiertas[0]
    raise HTTPException(404, "No hay hoja de ruta pendiente para hoy")


def en_ruta(placa: str) -> list[dict]:
    filas = hoja_activa(placa)
    if estado_hoja(filas) != "en_ruta":
        raise HTTPException(409, "Primero inicia el recorrido")
    return filas


def _filtro(q, h: dict):
    return q.eq("placa", h["placa"]).eq("fecha", h["fecha"]).eq("vuelta", h["vuelta"])


# --- modelos -----------------------------------------------------------------
class IniciarIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chofer_nombre: str = Field(min_length=2, max_length=60)


class Punto(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ts: datetime = Field(description="Hora del celular con zona, ISO 8601")
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    bateria: int | None = Field(default=None, ge=0, le=100)


class UbicacionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    puntos: list[Punto] = Field(min_length=1, max_length=500)


class LlegadaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    orden: int = Field(ge=1, description="Orden planificado de la parada")
    lat: float | None = None
    lon: float | None = None


class EntregaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    numero_doc: str
    estado: Literal["entregado", "no_entregado"]
    motivo: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def _motivo(self):
        if self.estado == "no_entregado" and not (self.motivo or "").strip():
            raise ValueError("motivo es obligatorio si no se entregó")
        return self


# --- endpoints ---------------------------------------------------------------
@router.get("/hoja-activa")
def ver_hoja_activa(u=Depends(requiere("chofer"))):
    return armar_hoja(hoja_activa(u["placa"]))


@router.post("/iniciar")
def iniciar(body: IniciarIn, bg: BackgroundTasks, u=Depends(requiere("chofer"))):
    filas = hoja_activa(u["placa"])
    h = armar_hoja(filas)
    if h["estado"] == "en_ruta":
        return h  # idempotente: la app puede reintentar
    ts = ahora().isoformat()
    _filtro(get_db().from_("asignaciones").update(
        {"chofer": body.chofer_nombre.strip(), "inicio_ts": ts}), h).execute()
    bg.add_task(avisar, "recorrido_iniciado",
                f"▶️ {h['placa']} (vuelta {h['vuelta']}) inició recorrido. "
                f"Chofer: {body.chofer_nombre.strip()}. {h['total_paradas']} paradas.")
    return armar_hoja(hoja_activa(u["placa"]))


@router.post("/ubicacion")
def ubicacion(body: UbicacionIn, u=Depends(requiere("chofer"))):
    """Acepta la cola acumulada sin señal. Reenviar el mismo punto no lo duplica."""
    h = armar_hoja(en_ruta(u["placa"]))
    filas = [{"placa": h["placa"], "fecha": h["fecha"], "vuelta": h["vuelta"], "chofer": h["chofer"],
              "ts": p.ts.isoformat(), "lat": p.lat, "lon": p.lon, "bateria": p.bateria}
             for p in body.puntos]
    get_db().from_("ubicaciones").upsert(filas, on_conflict="placa,ts", ignore_duplicates=True).execute()
    return {"recibidos": len(filas)}


@router.post("/llegada")
def llegada(body: LlegadaIn, bg: BackgroundTasks, u=Depends(requiere("chofer"))):
    filas = en_ruta(u["placa"])
    parada = [f for f in filas if f["orden"] == body.orden]
    if not parada:
        raise HTTPException(404, f"La parada {body.orden} no está en tu hoja")
    if parada[0]["orden_llegada"]:  # idempotente
        n = parada[0]["orden_llegada"]
        return {"orden": body.orden, "orden_llegada": n, "texto": ordinal(n)}
    n = len({f["orden"] for f in filas if f["orden_llegada"]}) + 1
    h = armar_hoja(filas)
    _filtro(get_db().from_("asignaciones").update(
        {"orden_llegada": n, "llegada_ts": ahora().isoformat()}), h).eq("orden", body.orden).execute()
    bg.add_task(avisar, "llegada",
                f"📍 {h['placa']}: {ordinal(n)} llegada → parada {body.orden} "
                f"(cliente {parada[0]['cliente_codigo']}).")
    return {"orden": body.orden, "orden_llegada": n, "texto": ordinal(n)}


@router.post("/entrega")
def entrega(body: EntregaIn, bg: BackgroundTasks, u=Depends(requiere("chofer"))):
    filas = en_ruta(u["placa"])
    doc = next((f for f in filas if f["numero_doc"] == body.numero_doc), None)
    if not doc:
        raise HTTPException(404, f"El documento {body.numero_doc} no está en tu hoja")
    if not doc["orden_llegada"]:
        raise HTTPException(409, "Marca primero la llegada a esa parada")
    get_db().from_("asignaciones").update({
        "estado": body.estado,
        "motivo": body.motivo if body.estado == "no_entregado" else None,
        "entregado_ts": ahora().isoformat(),
    }).eq("numero_doc", body.numero_doc).execute()
    if body.estado == "no_entregado":
        bg.add_task(avisar, "no_entregado",
                    f"⚠️ {doc['placa']}: documento {body.numero_doc} NO entregado "
                    f"(cliente {doc['cliente_codigo']}). Motivo: {body.motivo}")
    return {"numero_doc": body.numero_doc, "estado": body.estado}


@router.post("/finalizar")
def finalizar(bg: BackgroundTasks, u=Depends(requiere("chofer"))):
    h = armar_hoja(en_ruta(u["placa"]))
    _filtro(get_db().from_("asignaciones").update({"fin_ts": ahora().isoformat()}), h).execute()
    pend = h["total_documentos"] - h["entregados"] - h["no_entregados"]
    bg.add_task(avisar, "recorrido_finalizado",
                f"🏁 {h['placa']} (vuelta {h['vuelta']}) finalizó. Entregados {h['entregados']}, "
                f"no entregados {h['no_entregados']}, sin marcar {pend}.")
    return {"placa": h["placa"], "vuelta": h["vuelta"], "entregados": h["entregados"],
            "no_entregados": h["no_entregados"], "sin_marcar": pend}
