from datetime import date, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict

LIMA = ZoneInfo("America/Lima")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase (la service_role key SOLO vive en Render)
    supabase_url: str = ""
    supabase_service_key: str = ""
    # Solo para pruebas locales contra PostgREST directo (en Render se deja vacío)
    supabase_rest_url: str = ""

    jwt_secret: str = "cambiar-en-render"
    jwt_expire_min: int = 720          # 12 h: cubre la jornada del chofer

    # Usuarios de la demo:  usuario:clave:rol,usuario:clave:rol
    usuarios: str = ""
    # PIN por placa:  C4F-719:1234,ABC-123:5678
    placas_pin: str = ""

    cors_origins: str = "*"            # dominio de Netlify, separados por coma

    # CallMeBot:  +51999111222:apikey,+51999333444:apikey
    callmebot_destinatarios: str = ""
    callmebot_eventos: str = "hoja_creada,recorrido_iniciado,llegada,no_entregado,sin_gps,recorrido_finalizado"

    sin_gps_min: int = 20              # minutos sin punto GPS para avisar
    cron_key: str = ""                 # clave para /tareas/revisar-gps

    @property
    def rest_url(self) -> str:
        return self.supabase_rest_url or f"{self.supabase_url.rstrip('/')}/rest/v1"

    @staticmethod
    def _pares(texto: str) -> list[list[str]]:
        return [p.strip().split(":") for p in texto.split(",") if p.strip()]

    @property
    def usuarios_dict(self) -> dict[str, tuple[str, str]]:
        return {p[0]: (p[1], p[2]) for p in self._pares(self.usuarios) if len(p) == 3}

    @property
    def placas_dict(self) -> dict[str, str]:
        return {p[0].upper(): p[1] for p in self._pares(self.placas_pin) if len(p) == 2}

    @property
    def destinatarios(self) -> list[tuple[str, str]]:
        # el teléfono lleva "+", así que se separa por el último ":"
        out = []
        for item in self.callmebot_destinatarios.split(","):
            if ":" in item:
                tel, key = item.strip().rsplit(":", 1)
                out.append((tel, key))
        return out

    @property
    def eventos_aviso(self) -> set[str]:
        return {e.strip() for e in self.callmebot_eventos.split(",") if e.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()


def hoy_lima() -> date:
    return datetime.now(LIMA).date()


def ahora() -> datetime:
    return datetime.now(LIMA)
