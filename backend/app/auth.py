import hmac
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, ConfigDict

from .config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
bearer = HTTPBearer()
ALG = "HS256"


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    usuario: str
    clave: str


class ChoferIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    placa: str
    pin: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    rol: str
    placa: str | None = None


def _token(sub: str, rol: str, placa: str | None = None) -> str:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=s.jwt_expire_min)
    return jwt.encode({"sub": sub, "rol": rol, "placa": placa, "exp": exp}, s.jwt_secret, ALG)


def _igual(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn):
    reg = get_settings().usuarios_dict.get(body.usuario)
    if not reg or not _igual(reg[0], body.clave):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o clave incorrectos")
    return TokenOut(access_token=_token(body.usuario, reg[1]), rol=reg[1])


@router.post("/chofer", response_model=TokenOut)
def login_chofer(body: ChoferIn):
    placa = body.placa.strip().upper()
    pin = get_settings().placas_dict.get(placa)
    if not pin or not _igual(pin, body.pin):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Placa o PIN incorrectos")
    return TokenOut(access_token=_token(placa, "chofer", placa), rol="chofer", placa=placa)


def usuario_actual(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    try:
        return jwt.decode(cred.credentials, get_settings().jwt_secret, algorithms=[ALG])
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o vencido")


def requiere(*roles: str):
    """admin pasa siempre."""
    def dep(u: dict = Depends(usuario_actual)) -> dict:
        if u.get("rol") not in roles and u.get("rol") != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Sin permiso para esta acción")
        return u
    return dep
