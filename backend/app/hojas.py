"""Lógica compartida: una hoja de ruta = filas de asignaciones con la misma placa + fecha + vuelta."""
from collections import defaultdict
from datetime import date

from .db import get_db


def estado_hoja(filas: list[dict]) -> str:
    if any(f.get("fin_ts") for f in filas):
        return "finalizada"
    if any(f.get("inicio_ts") for f in filas):
        return "en_ruta"
    return "asignada"


def filas_hoja(placa: str, fecha: date | str, vuelta: int) -> list[dict]:
    return (
        get_db().from_("asignaciones").select("*")
        .eq("placa", placa).eq("fecha", str(fecha)).eq("vuelta", vuelta)
        .order("orden").order("numero_doc").execute().data
    )


def agrupar(filas: list[dict]) -> dict[tuple, list[dict]]:
    g: dict[tuple, list[dict]] = defaultdict(list)
    for f in filas:
        g[(f["placa"], f["fecha"], f["vuelta"])].append(f)
    return g


def armar_hoja(filas: list[dict]) -> dict:
    """Convierte las filas planas en hoja → paradas → documentos."""
    f0 = filas[0]
    paradas: dict[int, dict] = {}
    for f in sorted(filas, key=lambda x: (x["orden"], x["numero_doc"])):
        p = paradas.setdefault(f["orden"], {
            "orden": f["orden"], "cliente_codigo": f["cliente_codigo"],
            "lat": f["lat"], "lon": f["lon"],
            "orden_llegada": f["orden_llegada"], "llegada_ts": f["llegada_ts"],
            "documentos": [],
        })
        p["documentos"].append({
            "numero_doc": f["numero_doc"], "estado": f["estado"],
            "motivo": f["motivo"], "entregado_ts": f["entregado_ts"],
        })
    for p in paradas.values():
        estados = {d["estado"] for d in p["documentos"]}
        if estados == {"pendiente"}:
            p["estado"] = "llegó" if p["orden_llegada"] else "pendiente"
        elif "pendiente" in estados:
            p["estado"] = "en_proceso"
        elif "no_entregado" in estados:
            p["estado"] = "no_entregado"
        else:
            p["estado"] = "entregado"
    docs = [d for p in paradas.values() for d in p["documentos"]]
    return {
        "placa": f0["placa"], "fecha": f0["fecha"], "vuelta": f0["vuelta"],
        "estado": estado_hoja(filas), "chofer": f0.get("chofer"),
        "inicio_ts": f0.get("inicio_ts"), "fin_ts": f0.get("fin_ts"),
        "total_paradas": len(paradas), "total_documentos": len(docs),
        "entregados": sum(d["estado"] == "entregado" for d in docs),
        "no_entregados": sum(d["estado"] == "no_entregado" for d in docs),
        "paradas": list(paradas.values()),
    }
