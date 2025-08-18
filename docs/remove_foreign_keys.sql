-- Script para remover las foreign key constraints que impiden crear datos de prueba
-- Esto permite crear datos sin necesidad de auth.users

-- Remover foreign key constraints de todas las tablas
ALTER TABLE public.usuarios DROP CONSTRAINT IF EXISTS usuarios_auth_user_id_fkey;
ALTER TABLE public.info_contacto DROP CONSTRAINT IF EXISTS info_contacto_auth_user_id_fkey;
ALTER TABLE public.ubicaciones DROP CONSTRAINT IF EXISTS ubicaciones_auth_user_id_fkey;
ALTER TABLE public.origenes_botanicos DROP CONSTRAINT IF EXISTS origenes_botanicos_auth_user_id_fkey;
ALTER TABLE public.solicitudes_apicultor DROP CONSTRAINT IF EXISTS solicitudes_apicultor_auth_user_id_fkey;

-- Verificar que las constraints fueron removidas
SELECT 
    tc.table_name, 
    tc.constraint_name, 
    tc.constraint_type
FROM information_schema.table_constraints tc
WHERE tc.table_schema = 'public' 
AND tc.constraint_type = 'FOREIGN KEY'
AND tc.table_name IN ('usuarios', 'info_contacto', 'ubicaciones', 'origenes_botanicos', 'solicitudes_apicultor');
