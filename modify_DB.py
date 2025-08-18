"""
Módulo general para operaciones de escritura/modificación en la base de datos
Permite actualizar cualquier tabla/campo desde formularios JSON con manejo de RLS
"""

import logging
from typing import Dict, Any, Optional, Tuple
import json
from gmaps_utils import process_ubicacion_data
from auth_manager import AuthManager

logger = logging.getLogger(__name__)

class DatabaseModifier:
    """Clase principal para manejar todas las operaciones de escritura en la base de datos"""
    
    def get_authenticated_client(self):
        """Cliente Supabase autenticado único usando AuthManager"""
        return AuthManager.get_authenticated_client()
    
    def get_auth_user_id(self, auth_client, user_uuid):
        """Obtener el auth_user_id correspondiente al user_uuid"""
        try:
            # En el nuevo schema, user_uuid ES el auth_user_id
            user_info = auth_client.table('usuarios').select('auth_user_id').eq('auth_user_id', user_uuid).single().execute()
            return user_info.data['auth_user_id'] if user_info.data else None
        except Exception as e:
            logger.error(f"Error obteniendo auth_user_id: {e}")
            return None
    
    def get_current_user_uuid(self):
        """Obtener el UUID del usuario actual usando AuthManager"""
        return AuthManager.get_current_user_id()
    
    def validate_field(self, field_name, value, validation_rules=None):
        """Validar un campo según reglas específicas"""
        if not validation_rules:
            return True, None
            
        if 'min_length' in validation_rules and len(str(value)) < validation_rules['min_length']:
            return False, f"{field_name} debe tener al menos {validation_rules['min_length']} caracteres"
            
        if 'max_length' in validation_rules and len(str(value)) > validation_rules['max_length']:
            return False, f"{field_name} debe tener máximo {validation_rules['max_length']} caracteres"
            
        if 'required' in validation_rules and validation_rules['required'] and not value:
            return False, f"{field_name} es requerido"
            
        return True, None
    
    def check_unique_field(self, auth_client, table, field, value, exclude_auth_user_id=None):
        """Verificar si un valor es único en un campo específico"""
        try:
            # Select appropriate primary key field based on table
            if table == 'usuarios':
                pk_field = 'auth_user_id'
            elif table == 'info_contacto':
                pk_field = 'id'
            else:
                pk_field = 'id'
                
            query = auth_client.table(table).select(pk_field).eq(field, value)
            if exclude_auth_user_id:
                query = query.neq('auth_user_id', exclude_auth_user_id)
            
            result = query.execute()
            return len(result.data) == 0
        except Exception as e:
            logger.error(f"Error verificando unicidad: {e}")
            return False
    
    def update_record(self, table, data, user_uuid, field_mappings=None, validation_rules=None):
        """
        Función general para actualizar registros en cualquier tabla
        
        Args:
            table: Nombre de la tabla
            data: Diccionario con los datos a actualizar
            user_uuid: UUID del usuario (auth_user_id)
            field_mappings: Mapeo de campos permitidos y sus validaciones
            validation_rules: Reglas de validación específicas por campo
        """
        try:
            auth_client = self.get_authenticated_client()
            if not auth_client:
                return {"success": False, "error": "Error de autenticación"}, 401
            
            # Obtener auth_user_id para RLS
            auth_user_id = self.get_auth_user_id(auth_client, user_uuid)
            if not auth_user_id:
                return {"success": False, "error": "Usuario no encontrado"}, 404
            
            # Filtrar campos permitidos
            if field_mappings:
                update_data = {}
                current_record = {}
                
                # Obtener el registro actual
                if table == 'usuarios':
                    ref_field = 'auth_user_id'
                elif table == 'info_contacto':
                    ref_field = 'auth_user_id'
                else:
                    ref_field = 'auth_user_id'
                current_data = auth_client.table(table).select('*').eq(ref_field, user_uuid).execute()
                if current_data.data:
                    current_record = current_data.data[0]
                
                for field, value in data.items():
                    if field in field_mappings:
                        # Validar campo
                        rules = validation_rules.get(field, {}) if validation_rules else {}
                        is_valid, error_msg = self.validate_field(field, value, rules)
                        if not is_valid:
                            return {"success": False, "error": error_msg}, 400
                        
                        # Verificar unicidad si es necesario
                        if field_mappings.get(field, {}).get('unique', False):
                            unique = self.check_unique_field(auth_client, table, field, value, auth_user_id)
                            if not unique:
                                return {"success": False, "error": f"{field} ya existe"}, 400
                        
                        # IGNORAR COMPLETAMENTE campos vacíos o None - preservar datos existentes
                        if value is None:
                            continue
                            
                        new_value = str(value).strip()
                        
                        # SOLO actualizar si el nuevo valor tiene contenido real (no vacío)
                        if new_value != '':
                            update_data[field] = value
                        # Si el valor es vacío, ignorarlo completamente - NO actualizar ni sobrescribir
                
                # Si no hay datos válidos para actualizar (todos los campos eran vacíos)
                if not update_data:
                    logger.info("No hay datos válidos para actualizar - todos los campos estaban vacíos")
                    return {
                        "success": True,
                        "message": "No se realizaron cambios - los campos vacíos no sobrescriben datos existentes",
                        "data": current_data.data
                    }, 200
                
            else:
                # Permitir todos los campos si no hay mapeo específico
                update_data = data
            
            # Determinar campo de referencia según la tabla
            # En el nuevo schema, todas las tablas usan auth_user_id como referencia
            if table == 'usuarios':
                ref_field = 'auth_user_id'
                ref_value = user_uuid
            elif table == 'info_contacto':
                ref_field = 'auth_user_id'
                ref_value = user_uuid
            else:
                # Todas las demás tablas (ubicaciones, origenes_botanicos, solicitudes_apicultor)
                ref_field = 'auth_user_id'
                ref_value = user_uuid
            
            logger.info(f"Actualizando {table} para usuario {user_uuid} (auth_user_id: {auth_user_id})")
            logger.info(f"Datos a actualizar: {update_data}")
            
            # SOLUCIÓN RLS: Usar el usuario autenticado correctamente
            try:
                logger.info(f"=== DEBUG INICIO {table} ===")
                logger.info(f"Usuario UUID: {user_uuid}")
                logger.info(f"Campo ref: {ref_field} = {ref_value}")
                logger.info(f"Datos FINALES después de procesamiento: {json.dumps(update_data, ensure_ascii=False)}")
                
                if table == 'info_contacto':
                    # PASO CRÍTICO: Verificar que el usuario autenticado es el dueño
                    logger.info(f"Verificando ownership: auth_user_id={auth_user_id} vs user_uuid={user_uuid}")
                    
                    # Obtener el registro actual usando auth_user_id
                    ref_field = 'auth_user_id'
                    current_data = auth_client.table(table).select('*').eq(ref_field, user_uuid).execute()
                    logger.info(f"Datos actuales: {json.dumps(current_data.data, ensure_ascii=False)}")
                    
                    # Mapeo de campos por tabla
                    field_mapping = {
                        'usuarios': {
                            'nombre': 'nombre',
                            'apellido': 'apellido',
                            'email': 'email',
                            'telefono': 'telefono',
                            'nombre_empresa': 'nombre_empresa',
                            'rut': 'rut'
                        },
                        'info_contacto': {
                            'nombre_completo': 'nombre_completo',
                            'correo_principal': 'correo_principal',
                            'telefono_principal': 'telefono_principal',
                            'direccion': 'direccion',
                            'comuna': 'comuna',
                            'region': 'region',
                            'nombre_empresa': 'nombre_empresa'
                        },
                        'ubicaciones': {
                            'nombre': 'nombre',
                            'latitud': 'latitud',
                            'longitud': 'longitud',
                            'norma_geo': 'norma_geo',
                            'descripcion': 'descripcion'
                        }
                    }
                    
                    if not current_data.data or len(current_data.data) == 0:
                        logger.warning("Registro NO existe - CREANDO")
                        create_data = {
                            'auth_user_id': user_uuid,
                            'nombre_completo': update_data.get('nombre_completo', ''),
                            'correo_principal': update_data.get('correo_principal', ''),
                            'telefono_principal': update_data.get('telefono_principal', '')
                        }
                        create_data.update(update_data)
                        
                        insert_result = auth_client.table(table).insert(create_data).execute()
                        logger.info(f"Insert resultado: {json.dumps(insert_result.data, ensure_ascii=False)}")
                        
                        updated_data = auth_client.table(table).select('*').eq(ref_field, ref_value).single().execute()
                        logger.info(f"Datos después de insert: {json.dumps(updated_data.data, ensure_ascii=False)}")
                    else:
                        logger.info("Registro EXISTE - ACTUALIZANDO")
                        
                        # CRÍTICO: Verificar ownership - en el nuevo schema user_uuid ES auth_user_id
                        if str(user_uuid) != str(auth_user_id):
                            logger.error(f"❌ NO AUTORIZADO: user_uuid={user_uuid} no coincide con auth_user_id={auth_user_id}")
                            return {"success": False, "error": "Usuario no autorizado para modificar este registro"}, 403
                        
                        # Ejecutar update con usuario autenticado
                        update_result = auth_client.table(table).update(update_data).eq(ref_field, ref_value).execute()
                        
                        # Manejar respuesta vacía o lista
                        if hasattr(update_result, 'data') and update_result.data:
                            logger.info(f"Update resultado: {json.dumps(update_result.data, ensure_ascii=False)}")
                        else:
                            logger.info("Update ejecutado, verificando cambios...")
                        
                        # Verificar cambios reales
                        updated_data = auth_client.table(table).select('*').eq(ref_field, ref_value).single().execute()
                        if updated_data.data:
                            logger.info(f"Datos después de update: {json.dumps(updated_data.data, ensure_ascii=False)}")
                            return {"success": True, "data": updated_data.data}, 200
                        else:
                            logger.error("No se pudieron recuperar los datos actualizados")
                            return {"success": False, "error": "Error al recuperar datos actualizados"}, 500
                        
                        # Validar que cambió
                        if updated_data.data and updated_data.data[0] != current_data.data[0]:
                            logger.info("✅ CAMBIOS APLICADOS CORRECTAMENTE")
                        else:
                            logger.error("❌ NO HUBO CAMBIOS - VERIFICAR RLS POLICY")
                            # Intentar con upsert como fallback
                            upsert_result = auth_client.table(table).upsert({
                                **update_data,
                                'auth_user_id': user_uuid
                            }).execute()
                            logger.info(f"UPSERT RESULTADO: {json.dumps(upsert_result.data, ensure_ascii=False)}")
                
                else:
                    auth_client.table(table).update(update_data).eq(ref_field, ref_value).execute()
                    updated_data = auth_client.table(table).select('*').eq(ref_field, ref_value).single().execute()
                
                logger.info(f"=== DEBUG FIN {table} ===")
                return {
                    "success": True,
                    "message": f"{table} actualizado correctamente",
                    "data": updated_data.data
                }, 200
                        
            except Exception as e:
                logger.error(f"=== ERROR CRÍTICO {table} ===")
                logger.error(f"Error: {str(e)}")
                logger.error(f"Tipo: {type(e)}")
                return {"success": False, "error": f"Error al actualizar: {str(e)}"}, 500
            
            # Obtener datos actualizados
            updated_data = auth_client.table(table).select('*').eq(ref_field, ref_value).single().execute()
            
            return {
                "success": True,
                "message": f"{table} actualizado correctamente",
                "data": updated_data.data
            }, 200
            
        except Exception as e:
            logger.error(f"Error actualizando {table}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}, 500
    
    def insert_record(self, table, data, user_uuid=None):
        """Insertar un nuevo registro en cualquier tabla"""
        try:
            auth_client = self.get_authenticated_client()
            if not auth_client:
                return {"success": False, "error": "Error de autenticación"}, 401
            
            # Agregar usuario_id si se proporciona
            if user_uuid and 'usuario_id' not in data:
                data['usuario_id'] = user_uuid
            
            # Agregar timestamps
            data['created_at'] = datetime.utcnow().isoformat()
            data['updated_at'] = datetime.utcnow().isoformat()
            
            logger.info(f"Insertando en {table}: {data}")
            insert_result = auth_client.table(table).insert(data).execute()
            
            if not insert_result.data or len(insert_result.data) == 0:
                return {"success": False, "error": "No se pudo insertar el registro"}, 500
            
            return {
                "success": True,
                "message": f"Registro insertado en {table} correctamente",
                "data": insert_result.data[0]
            }, 200
            
        except Exception as e:
            logger.error(f"Error insertando en {table}: {e}")
            return {"success": False, "error": str(e)}, 500
    
    def get_record(self, table, user_uuid, select_fields='*'):
        """Obtener un registro de cualquier tabla"""
        try:
            auth_client = self.get_authenticated_client()
            if not auth_client:
                return []
            
            ref_field = 'usuario_id' if table != 'usuarios' else 'id'
            response = auth_client.table(table).select('*').eq(ref_field, user_uuid).execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            logger.error(f"Error obteniendo registros {table}: {e}")
            return []
    
    def get_records(self, table, user_uuid, select_fields='*'):
        """Obtener múltiples registros del usuario"""
        try:
            auth_client = self.get_authenticated_client()
            if not auth_client:
                return []
            
            ref_field = 'usuario_id' if table != 'usuarios' else 'id'
            response = auth_client.table(table).select('*').eq(ref_field, user_uuid).execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            logger.error(f"Error obteniendo registros {table}: {e}")
            return []

    def delete_record(self, table, user_uuid, extra_conditions=None):
        """Eliminar un registro de cualquier tabla"""
        try:
            auth_client = self.get_authenticated_client()
            if not auth_client:
                return {"success": False, "error": "Error de autenticación"}, 401
            
            # Determinar campo de referencia
            if table == 'usuarios':
                auth_user_id = self.get_auth_user_id(auth_client, user_uuid)
                if not auth_user_id:
                    return {"success": False, "error": "Usuario no encontrado"}, 404
                ref_field = 'auth_user_id'
                ref_value = auth_user_id
            else:
                ref_field = 'usuario_id'
                ref_value = user_uuid
            
            query = auth_client.table(table).delete().eq(ref_field, ref_value)
            
            # Agregar condiciones adicionales si existen
            if extra_conditions:
                for field, value in extra_conditions.items():
                    query = query.eq(field, value)
            
            delete_result = query.execute()
            
            return {
                "success": True,
                "message": f"Registro eliminado de {table} correctamente",
                "deleted_count": len(delete_result.data) if delete_result.data else 0
            }, 200
            
        except Exception as e:
            logger.error(f"Error eliminando de {table}: {e}")
            return {"success": False, "error": str(e)}, 500

# Instancia global para uso fácil
db_modifier = DatabaseModifier()

# Funciones de conveniencia para uso directo
def update_user_data(data, user_uuid):
    """Actualizar datos del usuario"""
    # Filtrar campos que no existen en la tabla
    allowed_fields = {'username', 'tipo_usuario', 'role', 'empresa', 'status'}
    filtered_data = {k: v for k, v in data.items() if k in allowed_fields}
    
    # Truncar automáticamente el campo role a 30 caracteres
    if 'role' in filtered_data and filtered_data['role']:
        original_role = str(filtered_data['role'])
        truncated_role = original_role[:30]
        logger.info(f"=== TRUNCAMIENTO ROLE ===")
        logger.info(f"Original: '{original_role}' ({len(original_role)} chars)")
        logger.info(f"Truncado: '{truncated_role}' ({len(truncated_role)} chars)")
        filtered_data['role'] = truncated_role
    
    field_mappings = {
        'username': {'unique': True},
        'tipo_usuario': {},
        'role': {},
        'empresa': {},
        'status': {}
    }
    
    validation_rules = {
        'username': {'min_length': 8, 'max_length': 100},
        'tipo_usuario': {'max_length': 100},
        'role': {'max_length': 100},
        'empresa': {'max_length': 100}
    }
    
    return db_modifier.update_record('usuarios', filtered_data, user_uuid, field_mappings, validation_rules)

def update_user_location(data, user_uuid):
    """Actualizar ubicación del usuario"""
    field_mappings = {
        'direccion': {},
        'ciudad': {},
        'provincia': {},
        'pais': {},
        'codigo_postal': {},
        'latitud': {},
        'longitud': {}
    }
    
    validation_rules = {
        'direccion': {'max_length': 255},
        'ciudad': {'max_length': 100},
        'provincia': {'max_length': 100},
        'pais': {'max_length': 100},
        'codigo_postal': {'max_length': 20}
    }
    
    return db_modifier.update_record('ubicaciones', data, user_uuid, field_mappings, validation_rules)

def update_user_contact(data, user_uuid):
    """Actualizar información de contacto del usuario"""
    field_mappings = {
        'nombre_completo': {},  # ¡FALTABA ESTE CAMPO!
        'nombre_empresa': {},
        'correo_principal': {},
        'telefono_principal': {},
        'correo_secundario': {},
        'telefono_secundario': {},
        'direccion': {},
        'comuna': {},
        'region': {},
        'pais': {}
    }
    
    validation_rules = {
        'correo_principal': {'max_length': 255},
        'telefono_principal': {'max_length': 50},
        'correo_secundario': {'max_length': 255},
        'telefono_secundario': {'max_length': 50},
        'sitio_web': {'max_length': 255}
    }
    
    return db_modifier.update_record('info_contacto', data, user_uuid, field_mappings, validation_rules)
