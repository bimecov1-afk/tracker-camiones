from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from postgrest.exceptions import APIError
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..auth import requiere
from ..config import get_settings, hoy_lima
from ..db import get_db
from ..hojas import agrupar, armar_hoja, estado_hoja, filas_hoja
from ..services.callmebot import avisar

router = APIRouter(tags=["despacho"])


class DocumentoIn(BaseModel):
    # extra="forbid": segunda barrera contra columnas sensibles (LOCAL_*, montos, nombres…)
    model_config = ConfigDict(extra="forbid")
    orden: int = Field(ge=1, le=99)
    numero_doc: str = Field(min_length=3, max_length=30)
    cliente_codigo: str = Field(min_length=1, max_length=20)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


class HojaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fecha: date
    placa: str
    vuelta: int | None = Field(default=None, ge=1, le=9, description="Vacío = siguiente vuelta libre")
    documentos: list[DocumentoIn] = Field(min_length=1, max_length=200)

    @field_validator("placa")
    @classmethod
    def _placa(cls, v: str) -> str:
        return v.strip().upper()


@router.get("/placas", summary="Placas habilitadas (para validar el Excel)")
def placas(_=Depends(requiere("despacho", "monitoreo"))):
    return sorted(get_settings().placas_dict)


@router.post("/hojas-ruta", status_code=201)
def crear_hoja(body: HojaIn, bg: BackgroundTasks, _=Depends(requiere("despacho"))):
    if body.placa not in get_settings().placas_dict:
        raise HTTPException(422, f"Placa {body.placa} no habilitada")
    nums = [d.numero_doc for d in body.documentos]
    dup = {n for n in nums if nums.count(n) > 1}
    if dup:
        raise HTTPException(422, f"Documentos repetidos en la hoja: {sorted(dup)}")

    db = get_db()
    existentes = (db.from_("asignaciones").select("vuelta")
                  .eq("placa", body.placa).eq("fecha", str(body.fecha)).execute().data)
    usadas = {r["vuelta"] for r in existentes}
    vuelta = body.vuelta or (max(usadas) + 1 if usadas else 1)
    if vuelta in usadas:
        raise HTTPException(409, f"La placa {body.placa} ya tiene la vuelta {vuelta} el {body.fecha}")

    filas = [{"fecha": str(body.fecha), "placa": body.placa, "vuelta": vuelta, **d.model_dump()}
             for d in body.documentos]
    try:
        db.from_("asignaciones").insert(filas).execute()
    except APIError as e:
        if e.code == "23505":
            ya = (db.from_("asignaciones").select("numero_doc,placa,fecha")
                  .in_("numero_doc", nums).execute().data)
            raise HTTPException(409, {"mensaje": "Documentos ya asignados", "documentos": ya})
        raise

    paradas = len({d.orden for d in body.documentos})
    bg.add_task(avisar, "hoja_creada",
                f"🚚 Hoja creada {body.placa} vuelta {vuelta} ({body.fecha}): "
                f"{paradas} paradas, {len(filas)} documentos.")
    return {"placa": body.placa, "fecha": body.fecha, "vuelta": vuelta,
            "paradas": paradas, "documentos": len(filas)}


@router.get("/hojas-ruta")
def listar_hojas(fecha: date | None = Query(None, description="Por defecto hoy (Lima)"),
                 _=Depends(requiere("despacho", "monitoreo"))):
    f = fecha or hoy_lima()
    filas = get_db().from_("asignaciones").select("*").eq("fecha", str(f)).execute().data
    hojas = [armar_hoja(v) for v in agrupar(filas).values()]
    for h in hojas:
        h.pop("paradas")
    return sorted(hojas, key=lambda h: (h["placa"], h["vuelta"]))


@router.get("/hojas-ruta/{placa}/{fecha}/{vuelta}")
def ver_hoja(placa: str, fecha: date, vuelta: int, _=Depends(requiere("despacho", "monitoreo"))):
    filas = filas_hoja(placa.upper(), fecha, vuelta)
    if not filas:
        raise HTTPException(404, "Hoja no encontrada")
    return armar_hoja(filas)


@router.delete("/hojas-ruta/{placa}/{fecha}/{vuelta}", status_code=204)
def borrar_hoja(placa: str, fecha: date, vuelta: int, _=Depends(requiere("despacho"))):
    placa = placa.upper()
    filas = filas_hoja(placa, fecha, vuelta)
    if not filas:
        raise HTTPException(404, "Hoja no encontrada")
    if estado_hoja(filas) != "asignada":
        raise HTTPException(409, "La hoja ya inició; no se puede borrar")
    (get_db().from_("asignaciones").delete()
     .eq("placa", placa).eq("fecha", str(fecha)).eq("vuelta", vuelta).execute())
