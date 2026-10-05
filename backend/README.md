# Backend · Tracker Camiones (FastAPI → Render)

Supabase guarda solo códigos por placa (`asignaciones`) y GPS (`ubicaciones`).
Una hoja de ruta = **placa + fecha + vuelta**. El contrato vive en `/docs` (Swagger).

## 1. Supabase
SQL Editor → ejecutar `db/03_vuelta.sql` (después de 01 y 02).
Copiar de *Project Settings → API*: **Project URL** y **service_role key**.

## 2. Render
1. Subir el repo a GitHub (`.env` nunca se sube).
2. Render → **New → Blueprint** → elegir el repo (lee `render.yaml` de la raíz).
   O bien **New → Web Service**, Root Directory `backend`,
   Build `pip install -r requirements.txt`,
   Start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
3. Variables de entorno:

| Variable | Ejemplo / nota |
|---|---|
| `SUPABASE_URL` | `https://xxxx.supabase.co` |
| `SUPABASE_SERVICE_KEY` | service_role key (secreta) |
| `JWT_SECRET` | Render la genera |
| `JWT_EXPIRE_MIN` | `720` (12 h) |
| `USUARIOS` | `despacho:Clave1:despacho,monitoreo:Clave2:monitoreo,admin:Clave3:admin` |
| `PLACAS_PIN` | `C4F-719:4719,ABC-123:1123` |
| `CORS_ORIGINS` | `*` para la demo; luego el dominio de Netlify |
| `CALLMEBOT_DESTINATARIOS` | `+51999111222:apikey` (varios separados por coma) |
| `CALLMEBOT_EVENTOS` | opcional; por defecto todos |
| `SIN_GPS_MIN` | `20` |
| `CRON_KEY` | Render la genera |
| `TZ` / `PYTHON_VERSION` | `America/Lima` / `3.12.7` |

4. Probar: `https://<servicio>.onrender.com/health` y `/docs`.

## 3. Aviso "sin GPS"
Crear un cron gratuito (cron-job.org) cada 10 min:
`POST https://<servicio>.onrender.com/tareas/revisar-gps` con header `x-cron-key: <CRON_KEY>`.
De paso mantiene despierto el plan gratuito de Render.

## 4. Prueba punta a punta
```
pip install httpx
set DESP_PASS=Clave1
set MONI_PASS=Clave2
python tests/recorrido_demo.py https://<servicio>.onrender.com
```
30 comprobaciones: login, rechazo de columnas `LOCAL_*`, crear hoja, iniciar,
cola GPS sin duplicados, llegadas 1ra/2da en orden real, entregas, monitoreo y finalizar.

## Endpoints
| Método | Ruta | Rol |
|---|---|---|
| POST | `/auth/login` | despacho, monitoreo, admin |
| POST | `/auth/chofer` | placa + PIN |
| GET | `/placas` | despacho, monitoreo |
| POST / GET | `/hojas-ruta` | despacho (GET también monitoreo) |
| GET / DELETE | `/hojas-ruta/{placa}/{fecha}/{vuelta}` | despacho (DELETE solo si no inició) |
| GET | `/chofer/hoja-activa` | chofer |
| POST | `/chofer/iniciar` · `/ubicacion` · `/llegada` · `/entrega` · `/finalizar` | chofer |
| GET | `/monitoreo/camiones?fecha=` | monitoreo |
| GET | `/hojas-ruta/{placa}/{fecha}/{vuelta}/recorrido` | monitoreo |
| POST | `/tareas/revisar-gps` | cron (`x-cron-key`) |
| GET | `/health` | público |

El chofer nunca envía su placa: va dentro del token, así no puede tocar otra hoja.
`admin` pasa todos los permisos.
