-- =============================================================================
-- Tracker Camiones · DEMO · 03_vuelta.sql
-- Una placa puede tener más de una hoja (vuelta) el mismo día.
-- La hoja de ruta se identifica por placa + fecha + vuelta.
-- También guarda el inicio/fin del recorrido y el nombre del chofer
-- (se repiten en las filas de la misma hoja; suficiente para la demo).
-- Ejecutar en Supabase → SQL Editor, después de 01 y 02.
-- =============================================================================

alter table public.asignaciones
  add column if not exists vuelta     smallint not null default 1,
  add column if not exists chofer     text,
  add column if not exists inicio_ts  timestamptz,
  add column if not exists fin_ts     timestamptz;

alter table public.ubicaciones
  add column if not exists fecha  date,
  add column if not exists vuelta smallint not null default 1;

drop index if exists public.asignaciones_placa_fecha_idx;
create index if not exists asignaciones_hoja_idx  on public.asignaciones (placa, fecha, vuelta);
create index if not exists ubicaciones_hoja_ts_idx on public.ubicaciones (placa, fecha, vuelta, ts);

-- Las filas de 02_demo.sql quedan como vuelta 1. Comprobar:
select placa, fecha, vuelta, count(*) as documentos
from public.asignaciones
group by placa, fecha, vuelta
order by fecha desc, placa, vuelta;
