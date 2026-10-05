"""Recorrido completo contra la API (local o Render).

    python tests/recorrido_demo.py http://localhost:8000
    python tests/recorrido_demo.py https://tracker-camiones-api.onrender.com

Variables opcionales: DESP_USER, DESP_PASS, MONI_USER, MONI_PASS, PLACA, PIN.
Usa la placa ABC-123 y crea documentos de prueba TEST-hhmmss-n. No borra nada al final;
para limpiar: delete from asignaciones where numero_doc like 'TEST-%';
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import httpx

API = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
c = httpx.Client(base_url=API, timeout=60)
PLACA, PIN = os.getenv("PLACA", "ABC-123"), os.getenv("PIN", "1123")
ok_total = 0


def check(nombre, r, esperado=200):
    global ok_total
    estado = "OK " if r.status_code == esperado else "ERR"
    ok_total += estado == "OK "
    print(f"[{estado}] {nombre:<42} {r.status_code}  {r.text[:110]}")
    if estado == "ERR":
        sys.exit(1)
    return r.json() if r.content else None


def h(tok):
    return {"Authorization": f"Bearer {tok}"}


check("health", c.get("/health"))
check("login clave incorrecta", c.post("/auth/login", json={"usuario": "despacho", "clave": "x"}), 401)
td = check("login despacho", c.post("/auth/login", json={
    "usuario": os.getenv("DESP_USER", "despacho"), "clave": os.getenv("DESP_PASS", "d1")}))["access_token"]
tm = check("login monitoreo", c.post("/auth/login", json={
    "usuario": os.getenv("MONI_USER", "monitoreo"), "clave": os.getenv("MONI_PASS", "m1")}))["access_token"]

hoy = datetime.now(timezone(timedelta(hours=-5))).date().isoformat()
sufijo = datetime.now().strftime("%H%M%S")
docs = [
    {"orden": 1, "numero_doc": f"TEST-{sufijo}-1", "cliente_codigo": "C1", "lat": -12.05, "lon": -77.04},
    {"orden": 2, "numero_doc": f"TEST-{sufijo}-2", "cliente_codigo": "C2", "lat": -12.06, "lon": -77.03},
    {"orden": 2, "numero_doc": f"TEST-{sufijo}-3", "cliente_codigo": "C2", "lat": -12.06, "lon": -77.03},
]
check("hoja con columna sensible → rechazada",
      c.post("/hojas-ruta", headers=h(td), json={"fecha": hoy, "placa": PLACA,
             "documentos": [{**docs[0], "LOCAL_monto": 3960}]}), 422)
check("hoja con placa no habilitada", c.post("/hojas-ruta", headers=h(td),
      json={"fecha": hoy, "placa": "ZZZ-999", "documentos": docs}), 422)
check("monitoreo no puede crear hojas", c.post("/hojas-ruta", headers=h(tm),
      json={"fecha": hoy, "placa": PLACA, "documentos": docs}), 403)
hoja = check("crear hoja", c.post("/hojas-ruta", headers=h(td),
             json={"fecha": hoy, "placa": PLACA, "documentos": docs}), 201)
check("documento repetido → 409", c.post("/hojas-ruta", headers=h(td),
      json={"fecha": hoy, "placa": PLACA, "documentos": docs[:1]}), 409)
check("listar hojas del día", c.get("/hojas-ruta", headers=h(td)))

check("chofer PIN incorrecto", c.post("/auth/chofer", json={"placa": PLACA, "pin": "0000"}), 401)
tc = check("login chofer", c.post("/auth/chofer", json={"placa": PLACA.lower(), "pin": PIN}))["access_token"]
check("chofer no entra a monitoreo", c.get("/monitoreo/camiones", headers=h(tc)), 403)
activa = check("hoja activa", c.get("/chofer/hoja-activa", headers=h(tc)))
check("llegada antes de iniciar → 409", c.post("/chofer/llegada", headers=h(tc), json={"orden": 1}), 409)
check("iniciar", c.post("/chofer/iniciar", headers=h(tc), json={"chofer_nombre": "Juan Pérez"}))

ahora = datetime.now(timezone.utc)
cola = [{"ts": (ahora - timedelta(minutes=5 * i)).isoformat(), "lat": -12.05 + i / 1000,
         "lon": -77.04, "bateria": 80 - i} for i in range(3, 0, -1)]
check("ubicación (cola de 3 puntos)", c.post("/chofer/ubicacion", headers=h(tc), json={"puntos": cola}))
check("reenvío de la cola (sin duplicar)", c.post("/chofer/ubicacion", headers=h(tc), json={"puntos": cola}))

r2 = check("llegada parada 2 (primero)", c.post("/chofer/llegada", headers=h(tc), json={"orden": 2}))
r1 = check("llegada parada 1 (después)", c.post("/chofer/llegada", headers=h(tc), json={"orden": 1}))
assert r2["texto"] == "1ra" and r1["texto"] == "2da", (r2, r1)
check("llegada repetida (idempotente)", c.post("/chofer/llegada", headers=h(tc), json={"orden": 2}))
check("doc de otra hoja → 404", c.post("/chofer/entrega", headers=h(tc),
      json={"numero_doc": "T001-000452", "estado": "entregado"}), 404)
check("no entregado sin motivo → 422", c.post("/chofer/entrega", headers=h(tc),
      json={"numero_doc": docs[1]["numero_doc"], "estado": "no_entregado"}), 422)
check("entregado", c.post("/chofer/entrega", headers=h(tc),
      json={"numero_doc": docs[0]["numero_doc"], "estado": "entregado"}))
check("entregado", c.post("/chofer/entrega", headers=h(tc),
      json={"numero_doc": docs[1]["numero_doc"], "estado": "entregado"}))
check("no entregado con motivo", c.post("/chofer/entrega", headers=h(tc),
      json={"numero_doc": docs[2]["numero_doc"], "estado": "no_entregado", "motivo": "Local cerrado"}))

cam = check("monitoreo: camiones", c.get("/monitoreo/camiones", headers=h(tm)))
yo = next(x for x in cam if x["placa"] == PLACA and x["vuelta"] == hoja["vuelta"])
assert yo["estado"] == "en_ruta" and yo["ultimo_punto"], yo
rec = check("monitoreo: recorrido", c.get(f"/hojas-ruta/{PLACA}/{hoy}/{hoja['vuelta']}/recorrido", headers=h(tm)))
assert len(rec["puntos"]) == 3, len(rec["puntos"])
check("finalizar", c.post("/chofer/finalizar", headers=h(tc)))
check("borrar hoja ya iniciada → 409",
      c.delete(f"/hojas-ruta/{PLACA}/{hoy}/{hoja['vuelta']}", headers=h(td)), 409)
print(f"\n{ok_total} comprobaciones OK · hoja {PLACA} vuelta {hoja['vuelta']} del {hoy}")
