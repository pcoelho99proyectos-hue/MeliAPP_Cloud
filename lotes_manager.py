"""
Módulo para gestionar lotes de miel con control de orden secuencial.
"""
import uuid
import json
import re
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from supabase_client import SupabaseClient
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session
from modify_DB import DatabaseModifier, db_modifier

logger = logging.getLogger(__name__)

class LotesManager:
    """Gestiona la creación, edición y reordenamiento de lotes de miel."""
    
    def __init__(self, supabase_client):
        """Inicializa con cliente Supabase."""
        self.client = supabase_client
    
    def obtener_lotes_usuario(self, usuario_id: str) -> List[Dict[str, Any]]:
        """Obtiene todos los lotes de miel de un usuario ordenados por orden_miel."""
        try:
            # Usar DatabaseModifier para obtener un cliente autenticado
            db_modifier = DatabaseModifier()
            auth_client = db_modifier.get_authenticated_client()

            if not auth_client:
                logger.error("No se pudo obtener un cliente autenticado.")
                return []

            # Realizar la consulta con el cliente autenticado
            response = auth_client.table('origenes_botanicos').select('*').eq('auth_user_id', usuario_id).order('orden_miel').execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            logger.error(f"Error al obtener lotes: {str(e)}")
            return []
    
    def crear_lote(self, datos_lote: Dict[str, Any]) -> Dict[str, Any]:
        """Crea un nuevo lote de miel con orden manual único."""
        try:
            auth_user_id = datos_lote.get('auth_user_id')
            if not auth_user_id:
                return {'success': False, 'error': 'ID de usuario no proporcionado.'}

            # Validar datos de entrada
            errores_val = self._validar_datos_lote(datos_lote)
            if errores_val:
                return {'success': False, 'error': '; '.join(errores_val)}

            # Validar orden manual
            orden_miel = datos_lote.get('orden_miel')
            if not orden_miel:
                return {'success': False, 'error': 'Número de orden es requerido.'}
            
            try:
                orden_miel = int(orden_miel)
                if orden_miel <= 0:
                    return {'success': False, 'error': 'El número de orden debe ser mayor a 0.'}
            except (ValueError, TypeError):
                return {'success': False, 'error': 'El número de orden debe ser un número válido.'}

            # Verificar que el orden no esté duplicado para este usuario usando DatabaseModifier
            db_modifier_instance = DatabaseModifier()
            auth_client = db_modifier_instance.get_authenticated_client()
            
            if not auth_client:
                return {'success': False, 'error': 'Error de autenticación para validación'}
                
            orden_existente = auth_client.table('origenes_botanicos') \
                .select('id') \
                .eq('auth_user_id', auth_user_id) \
                .eq('orden_miel', orden_miel) \
                .execute()

            if orden_existente.data:
                return {'success': False, 'error': f'Ya existe un lote con el número de orden {orden_miel}. Por favor, elija un número diferente.'}

            # Verificar duplicado por nombre y temporada usando DatabaseModifier
            nombre_miel = datos_lote['nombre_miel'].strip()
            temporada = datos_lote['temporadas']

            existente = auth_client.table('origenes_botanicos') \
                .select('id') \
                .eq('auth_user_id', auth_user_id) \
                .eq('nombre_miel', nombre_miel) \
                .eq('temporada', temporada) \
                .execute()

            if existente.data:
                return {'success': False, 'error': f'Ya existe un lote con el nombre "{nombre_miel}" para la temporada "{temporada}".'}
            
            # Manejar composición polínica según el formato recibido (puede ser string o dict)
            composicion_data = datos_lote.get('composicion_polen', datos_lote.get('composicion', ''))
            
            # Si ya viene como string formateado (desde el frontend), usarlo directamente
            if isinstance(composicion_data, str):
                composicion_str = composicion_data
            # Si viene como diccionario, formatearlo como string
            elif isinstance(composicion_data, dict):
                composicion_str = ', '.join([f"{k}: {v}" for k, v in composicion_data.items()])
            else:
                composicion_str = ''

            nuevo_lote = {
                'auth_user_id': auth_user_id,
                'nombre_miel': nombre_miel,
                'temporada': temporada,
                'kg_producidos': float(datos_lote['kg_producidos']),
                'composicion': composicion_str,
                'fecha_registro': datos_lote.get('fecha_registro'),
                'orden_miel': orden_miel
            }

            # Usar db_modifier para la inserción
            resultado, status_code = db_modifier.insert_record(
                table='origenes_botanicos',
                data=nuevo_lote,
                user_uuid=auth_user_id
            )

            if resultado.get('success'):
                return {'success': True, 'lote': resultado['data'], 'message': 'Lote creado exitosamente.'}
            else:
                logger.error(f"Fallo al insertar lote vía db_modifier: {resultado.get('error')}")
                return {'success': False, 'error': resultado.get('error', 'Error desconocido al crear el lote.')}

        except Exception as e:
            logger.error(f"Excepción al crear lote: {e}", exc_info=True)
            return {'success': False, 'error': 'Ocurrió un error inesperado en el servidor.'}
    
    def actualizar_lote(self, lote_id: str, usuario_id: str, datos: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza un lote existente validando orden único."""
        try:
            # Verificar que el lote pertenece al usuario usando DatabaseModifier
            db_modifier_instance = DatabaseModifier()
            auth_client = db_modifier_instance.get_authenticated_client()
            
            if not auth_client:
                return {'success': False, 'error': 'Error de autenticación'}
                
            lote_actual = auth_client.table('origenes_botanicos') \
                .select('*') \
                .eq('id', lote_id) \
                .eq('auth_user_id', usuario_id) \
                .single() \
                .execute()
            
            if not lote_actual.data:
                return {'success': False, 'error': 'Lote no encontrado'}
            
            # Validar datos
            errores = self._validar_datos_lote(datos)
            if errores:
                return {'success': False, 'error': '; '.join(errores)}
            
            # Validar orden manual si se proporciona
            orden_miel = datos.get('orden_miel')
            if orden_miel is not None:
                try:
                    orden_miel = int(orden_miel)
                    if orden_miel <= 0:
                        return {'success': False, 'error': 'El número de orden debe ser mayor a 0.'}
                except (ValueError, TypeError):
                    return {'success': False, 'error': 'El número de orden debe ser un número válido.'}

                # Verificar que el orden no esté duplicado (excluyendo el lote actual)
                orden_existente = auth_client.table('origenes_botanicos') \
                    .select('id') \
                    .eq('auth_user_id', usuario_id) \
                    .eq('orden_miel', orden_miel) \
                    .neq('id', lote_id) \
                    .execute()

                if orden_existente.data:
                    return {'success': False, 'error': f'Ya existe otro lote con el número de orden {orden_miel}. Por favor, elija un número diferente.'}
            
            # Preparar datos para actualizar según esquema real
            fecha_actualizacion = datetime.now().strftime('%Y-%m-%d')  # Formato ISO
            
            # Manejar composición polínica según el formato recibido (puede ser string o dict)
            composicion_data = datos.get('composicion_polen', datos.get('composicion', ''))
            
            # Si ya viene como string formateado (desde el frontend), usarlo directamente
            if isinstance(composicion_data, str):
                composicion_str = composicion_data
            # Si viene como diccionario, formatearlo como string
            elif isinstance(composicion_data, dict):
                composicion_str = ', '.join([f"{k}: {v}" for k, v in composicion_data.items()])
            else:
                composicion_str = ''

            datos_actualizar = {
                'nombre_miel': datos['nombre_miel'].strip(),
                'temporada': datos['temporadas'],  # Múltiples temporadas
                'kg_producidos': float(datos['kg_producidos']),
                'composicion': composicion_str,  # Campo correcto según esquema DB
                'fecha_actualizacion': fecha_actualizacion
            }
            # NOTA: fecha_registro NO se incluye - debe permanecer INMUTABLE
            
            # Agregar orden_miel solo si se proporciona
            if orden_miel is not None:
                datos_actualizar['orden_miel'] = orden_miel
            
            # Usar db_modifier para la actualización con permisos adecuados
            # Nota: update_record no acepta record_id, usa el auth_user_id para filtrar
            # Necesitamos usar el método directo con cliente autenticado
            resultado = auth_client.table('origenes_botanicos') \
                .update(datos_actualizar) \
                .eq('id', lote_id) \
                .eq('auth_user_id', usuario_id) \
                .execute()
            
            if hasattr(resultado, 'error') and resultado.error:
                logger.error(f"Error en la actualización: {resultado.error}")
                return {'success': False, 'error': f"Error al actualizar: {resultado.error}"}
            
            if resultado.data:
                return {
                    'success': True,
                    'lote': resultado.data[0],
                    'message': 'Lote actualizado exitosamente'
                }
            else:
                return {'success': False, 'error': 'No se pudo actualizar el lote'}
                
        except Exception as e:
            logger.error(f"Error al actualizar lote: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def eliminar_lote(self, lote_id: str, usuario_id: str) -> Dict[str, Any]:
        """Elimina un lote directamente sin reordenamiento automático."""
        try:
            logger.info(f"==== INICIO ELIMINACIÓN LOTE ID: {lote_id} USUARIO: {usuario_id} =====")
            
            # Usar DatabaseModifier para la eliminación con permisos adecuados
            db_modifier_instance = DatabaseModifier()
            
            # Usar el método delete_record del módulo centralizado
            resultado, status_code = db_modifier_instance.delete_record(
                table='origenes_botanicos',
                user_uuid=usuario_id,
                extra_conditions={'id': lote_id}
            )
            
            if resultado.get('success'):
                logger.info(f"Lote eliminado exitosamente vía DatabaseModifier")
                return {
                    'success': True,
                    'message': 'Lote eliminado exitosamente.',
                    'deleted_count': resultado.get('deleted_count', 1)
                }
            else:
                logger.error(f"Fallo al eliminar lote vía DatabaseModifier: {resultado.get('error')}")
                return {'success': False, 'error': resultado.get('error', 'Error desconocido al eliminar el lote.')}
                
        except Exception as e:
            logger.error(f"Error inesperado al eliminar lote: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {'success': False, 'error': str(e)}

    def obtener_especies_por_zona(self, usuario_id: str) -> Dict[str, Any]:
        """Obtiene las especies florales según la zona geográfica del usuario con debug completo."""
        try:
            logger.info(f"=== DEBUG ESPECIES POR ZONA ===")            
            logger.info(f" Buscando especies para usuario: {usuario_id}")
            
            # 1. Obtener información de contacto del usuario usando la función RPC segura
            profile_response = self.client.rpc('get_user_profile', {'p_auth_user_id': usuario_id}).execute()

            if not profile_response.data:
                logger.warning(f" No se encontró perfil para el usuario {usuario_id} usando RPC.")
                return {
                    'success': False,
                    'message': 'Usuario no encontrado en sistema',
                    'especies': [],
                    'comuna': None
                }

            profile_data = profile_response.data
            contact_info = profile_data.get('info_contacto')
            comuna = contact_info.get('comuna') if contact_info else None
            logger.info(f" Comuna detectada: {comuna}")
            
            if not comuna:
                logger.warning(f" Usuario {usuario_id} no tiene comuna registrada")
                return {
                    'success': False,
                    'message': 'Usuario no tiene comuna registrada',
                    'especies': [],
                    'comuna': None
                }
            
            # 2. Obtener especies del CSV usando botanical_chart
            from botanical_chart import read_botanical_classes
            
            try:
                classes_data = read_botanical_classes()
                logger.info(f" Datos CSV cargados: {len(classes_data)} comunas disponibles")
                
                if comuna in classes_data:
                    # Extraer todas las especies de todas las clases para esta comuna
                    especies = []
                    for clase, especies_clase in classes_data[comuna].items():
                        especies.extend(especies_clase)
                    
                    # Remover duplicados manteniendo orden
                    especies = list(dict.fromkeys(especies))
                    logger.info(f" Especies del CSV para {comuna}: {especies}")
                    
                else:
                    logger.warning(f" Comuna {comuna} no encontrada en CSV")
                    especies = []
                    
            except Exception as csv_error:
                logger.error(f" Error al cargar CSV: {csv_error}")
                especies = []
            logger.info(f" Especies encontradas para {comuna}: {especies}")
            logger.info(f" Total especies disponibles: {len(especies)}")
            
            if especies:
                return {
                    'success': True,
                    'usuario_id': usuario_id,
                    'comuna': comuna,
                    'especies': especies,
                    'total_especies': len(especies),
                    'message': f'Especies disponibles para {comuna}'
                }
            else:
                logger.warning(f" No hay especies registradas para la comuna: {comuna}")
                return {
                    'success': False,
                    'usuario_id': usuario_id,
                    'comuna': comuna,
                    'especies': [],
                    'total_especies': 0,
                    'message': f'No hay especies registradas para {comuna}'
                }
            
        except Exception as e:
            logger.error(f" Error al obtener especies para usuario {usuario_id}: {str(e)}")
            return {
                'success': False,
                'message': f'Error al obtener especies: {str(e)}',
                'especies': [],
                'comuna': None
            }

    def _validar_datos_lote(self, datos: Dict[str, Any]) -> List[str]:
        """Valida los datos de entrada para un lote."""
        errores = []
        
        # Validar nombre de miel
        if not datos.get('nombre_miel', '').strip():
            errores.append("El nombre de la miel es requerido")
        
        # Validar temporada
        if not datos.get('temporadas'):
            errores.append("La temporada es requerida")
        
        # Validar kg producidos
        try:
            kg = float(datos.get('kg_producidos', 0))
            if kg <= 0:
                errores.append("Los kg producidos deben ser mayor a 0")
        except (ValueError, TypeError):
            errores.append("Los kg producidos deben ser un número válido")
        
        # Validar composición polínica si se proporciona
        composicion = datos.get('composicion_polen', datos.get('composicion'))
        if composicion:
            if isinstance(composicion, dict):
                total = 0
                for especie, porcentaje in composicion.items():
                    try:
                        valor = float(porcentaje)
                        if valor < 0 or valor > 100:
                            errores.append(f"El porcentaje para {especie} debe estar entre 0 y 100")
                        total += valor
                    except (ValueError, TypeError):
                        errores.append(f"El porcentaje para {especie} debe ser un número válido")
                
                # Validar que la suma no exceda 100%
                if total > 100:
                    errores.append("La suma de porcentajes de polen no puede exceder 100%")
                
                # Validar que haya al menos una especie si se proporciona composición
                if 'composicion' in datos and not composicion:
                    errores.append("La composición polínica no puede estar vacía si se proporciona")
        
        return errores

# Instancia global
from supabase_client import db
lotes_manager = LotesManager(db.client)
