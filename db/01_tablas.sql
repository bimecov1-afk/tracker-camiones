-- =============================================================================
-- Tracker Camiones · DEMO · 01_tablas.sql
-- Supabase solo guarda dos cosas, siempre por placa y solo con códigos:
--   1. asignaciones → qué guías/facturas lleva cada placa y su estado
--   2. ubicaciones  → el GPS que envía el celular cada 5 minutos
-- Nada de montos, nombres de clientes ni direcciones: eso queda en el Excel local.
-- Ejecutar en Supabase → SQL Editor.
-- =============================================================================

-- 1. Documentos asignados a cada placa ----------------------------------------
create table public.asignaciones (
  id             bigint generated always as identity primary key,
  fecha          date not null,
  placa          text not null,                 -- C4F-719
  orden          smallint not null,             -- orden planificado de la parada
  numero_doc     text not null unique,          -- T001-000452 (código de la guía o factura)
  cliente_codigo text not null,                 -- C00123 (solo el código)
  lat            double precision,              -- opcional, para ubicar la parada en el mapa
  lon            double precision,
  estado         text not null default 'pendiente'
                   check (estado in ('pendiente', 'entregado', 'no_entregado')),
  motivo         text,                          -- si no se entregó
  orden_llegada  smallint,                      -- 1ra, 2da, 3ra… según llegada real
  llegada_ts     timestamptz,
  entregado_ts   timestamptz,
  creado_en      timestamptz not null default now()
);
create index asignaciones_placa_fecha_idx on public.asignaciones (placa, fecha);

-- 2. Ubicación GPS por placa ----------------------------------------------------
create table public.ubicaciones (
  id             bigint generated always as identity primary key,
  placa          text not null,
  chofer         text,                          -- nombre que escribe el chofer al iniciar
  ts             timestamptz not null,          -- hora del celular (sirve para la cola sin señal)
  lat            double precision not null,
  lon            double precision not null,
  bateria        smallint,
  unique (placa, ts)                            -- reenviar la cola no duplica puntos
);

-- 3. Seguridad: solo el backend (service_role key) lee y escribe ----------------
alter table public.asignaciones enable row level security;
alter table public.ubicaciones  enable row level security;
revoke all on public.asignaciones, public.ubicaciones from anon, authenticated;
