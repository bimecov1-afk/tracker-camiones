import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import auth
from .config import ahora, get_settings
from .routers import chofer, despacho, monitoreo

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Tracker Camiones · API",
    version="0.1.0-demo",
    description="Backend de la demo. Supabase solo guarda códigos por placa (asignaciones) y GPS (ubicaciones).",
)

origins = [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

app.include_router(auth.router)
app.include_router(despacho.router)
app.include_router(chofer.router)
app.include_router(monitoreo.router)


@app.get("/health", tags=["público"])
def health():
    return {"ok": True, "hora_lima": ahora().isoformat(timespec="seconds")}
