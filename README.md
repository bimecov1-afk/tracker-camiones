# tracker-camiones

Seguimiento de la distribución de Rinti (demo). Un solo repositorio para todas las piezas:

| Carpeta | Pieza | Despliegue | Estado |
|---|---|---|---|
| `db/` | Scripts SQL de Supabase (01 tablas, 02 demo, 03 vuelta) | Supabase SQL Editor | F1 hecho · 03 por ejecutar |
| `backend/` | API FastAPI | Render (`render.yaml`) | F2 listo para desplegar |
| `despacho-local/` | App Streamlit que lee el Excel | PC de despacho | F3 pendiente |
| `web-monitoreo/` | Mapa Leaflet | Netlify | F4 pendiente |
| `android/` | App del chofer (Kotlin) | APK | F5 pendiente |

Plan de trabajo completo: proyecto *Tracking Mionka* (`PLAN_DE_TRABAJO.md`).
Pasos de despliegue del backend: [`backend/README.md`](backend/README.md).

Nunca subir archivos `.env` ni la `service_role key` de Supabase.
