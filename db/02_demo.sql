-- =============================================================================
-- Tracker Camiones · DEMO · 02_demo.sql
-- Hoja de la demo para hoy: placa C4F-719, 3 paradas, 5 documentos.
-- =============================================================================

insert into public.asignaciones (fecha, placa, orden, numero_doc, cliente_codigo, lat, lon) values
  ((now() at time zone 'America/Lima')::date, 'C4F-719', 1, 'T001-000452', 'C00123', -12.0301, -77.0712),
  ((now() at time zone 'America/Lima')::date, 'C4F-719', 1, 'F001-001208', 'C00123', -12.0301, -77.0712),
  ((now() at time zone 'America/Lima')::date, 'C4F-719', 2, 'T001-000453', 'C00456', -11.9905, -77.0705),
  ((now() at time zone 'America/Lima')::date, 'C4F-719', 3, 'T001-000454', 'C00789', -11.9452, -77.0583),
  ((now() at time zone 'America/Lima')::date, 'C4F-719', 3, 'F001-001209', 'C00789', -11.9452, -77.0583)
on conflict (numero_doc) do nothing;

-- Comprobar
select placa, orden, numero_doc, cliente_codigo, estado
from public.asignaciones
order by placa, orden, numero_doc;
