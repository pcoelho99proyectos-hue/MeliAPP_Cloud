"""
Módulo para gestionar lotes de miel con control de orden secuencial.
"""
import uuid
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging
from modify_DB import DatabaseModifier

logger = logging.getLogger(__name__)

class LotesManager:
    """Gestiona la creación, edición y reordenamiento de lotes de miel."""
    
    def __init__(self, supabase_client):
        """Inicializa con cliente Supabase."""
        self.client = supabase_client
    
    def obtener_lotes_usuario(self, usuario_id: str) -> List[Dict[str, Any]]:
        """Obtiene todos los lotes de miel de un usuario ordenados por orden_miel."""
        try:
            # Usar consulta directa a la tabla origenes_botanicos
            response = self.client.table('origenes_botanicos').select('*').eq('auth_user_id', usuario_id).order('orden_miel').execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            logger.error(f"Error al obtener lotes: {str(e)}")
            return []
    
    def crear_lote(self, usuario_id: str, datos: Dict[str, Any]) -> Dict[str, Any]:
        """Crea un nuevo lote de miel con el siguiente orden secuencial."""
        try:
            # DEBUG: Verificar datos recibidos
            logger.info(f"=== DEBUG CREAR LOTE ===")
            logger.info(f"usuario_id recibido: {usuario_id}")
            logger.info(f"datos completos: {json.dumps(datos, indent=2)}")
            logger.info(f"tipo usuario_id: {type(usuario_id)}")
            
            # Obtener el siguiente orden
            lotes_actuales = self.obtener_lotes_usuario(usuario_id)
            siguiente_orden = len(lotes_actuales) + 1
            
            # Validar datos
            errores = self._validar_datos_lote(datos)
            if errores:
                logger.error(f"Errores de validación: {errores}")
                return {'success': False, 'error': '; '.join(errores)}
            
            # Preparar datos para la inserción
            composicion_polen = datos.get('composicion_polen', {})
            if isinstance(composicion_polen, str):
                try:
                    composicion_polen = json.loads(composicion_polen)
                except json.JSONDecodeError:
                    composicion_polen = {}
            elif not isinstance(composicion_polen, dict):
                composicion_polen = {}
            
            # Asegurar formato correcto para temporada (solo primera temporada)
            temporada = datos['temporadas']
            if ',' in str(temporada):
                temporada = str(temporada).split(',')[0].strip()
            
            datos_lote = {
                'auth_user_id': usuario_id,
                'nombre_miel': datos['nombre_miel'],
                'temporada': temporada,  # Solo la primera temporada para cumplir con constraint
                'kg_producidos': float(datos['kg_producidos']),
                'orden_miel': siguiente_orden,
                'composicion_polen': composicion_polen,
                'fecha_registro': datos['fecha_registro']  # Fecha manual en formato ISO
            }
            
            logger.info(f"Datos a insertar: {json.dumps(datos_lote, indent=2)}")
            
            # Usar DatabaseModifier para operación autenticada
            db_modifier = DatabaseModifier()
            auth_client = db_modifier.get_authenticated_client()
            
            response = auth_client.table('origenes_botanicos').insert(datos_lote).execute()

            logger.info(f"Respuesta de Supabase: {response.data}")
            
            if response.data and len(response.data) > 0:
                lote_data = response.data[0]
                # Manejar diferentes estructuras de respuesta
                lote_id = lote_data.get('id')
                orden = lote_data.get('orden_miel')
                
                return {
                    'success': True,
                    'lote': {
                        'id': lote_id,
                        'auth_user_id': usuario_id,
                        'nombre_miel': datos['nombre_miel'],
                        'temporada': datos['temporadas'],
                        'kg_producidos': datos['kg_producidos'],
                        'orden_miel': orden,
                        'composicion_polen': composicion_polen,
                        'fecha_registro': datos['fecha_registro']
                    },
                    'message': f'Lote creado exitosamente con orden #{orden}'
                }
            else:
                return {'success': False, 'error': 'No se pudo crear el lote'}
                
        except Exception as e:
            logger.error(f"Error al crear lote: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def actualizar_lote(self, lote_id: str, usuario_id: str, datos: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza un lote existente manteniendo el orden."""
        try:
            # Verificar que el lote pertenece al usuario usando auth_user_id
            lote_actual = self.client.table('origenes_botanicos') \
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
            
            # Preparar datos para actualizar según esquema real
            fecha_actualizacion = datetime.now().strftime('%Y-%m-%d')  # Formato ISO
            
            datos_actualizar = {
                'nombre_miel': datos['nombre_miel'].strip(),
                'temporada': datos['temporadas'],  # Múltiples temporadas
                'kg_producidos': float(datos['kg_producidos']),
                'composicion_polen': datos.get('composicion_polen', {}),
                'fecha_registro': datos.get('fecha_registro'),  # Fecha manual en formato ISO
                'fecha_actualizacion': fecha_actualizacion
            }
            
            response = self.client.table('origenes_botanicos') \
                .update(datos_actualizar) \
                .eq('id', lote_id) \
                .execute()
            
            if response.data:
                return {
                    'success': True,
                    'lote': response.data[0],
                    'message': 'Lote actualizado exitosamente'
                }
            else:
                return {'success': False, 'error': 'No se pudo actualizar el lote'}
                
        except Exception as e:
            logger.error(f"Error al actualizar lote: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def eliminar_lote(self, lote_id: str, usuario_id: str) -> Dict[str, Any]:
        """Elimina un lote y reordena los lotes restantes usando función SQL."""
        try:
            # Usar función SQL con SECURITY DEFINER para evitar error 42501
            response = self.client.rpc('eliminar_lote_directo', {
                'p_lote_id': lote_id,
                'p_usuario_id': usuario_id
            }).execute()
            
            logger.info(f"Respuesta de eliminar_lote_directo: {response.data}")
            
            if response.data and len(response.data) > 0:
                resultado = response.data[0]
                if resultado.get('success'):
                    return {
                        'success': True,
                        'message': resultado.get('mensaje', 'Lote eliminado exitosamente'),
                        'orden_eliminado': resultado.get('orden_eliminado')
                    }
                else:
                    return {
                        'success': False,
                        'error': resultado.get('mensaje', 'Error al eliminar el lote')
                    }
            else:
                return {'success': False, 'error': 'No se pudo eliminar el lote'}
                
        except Exception as e:
            logger.error(f"Error al eliminar lote: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def reordenar_lotes(self, usuario_id: str, nuevo_orden: List[str]) -> Dict[str, Any]:
        """Reordena los lotes según el nuevo orden proporcionado."""
        try:
            # Obtener todos los lotes
            lotes = self.obtener_lotes_usuario(usuario_id)
            
            if len(lotes) != len(nuevo_orden):
                return {'success': False, 'error': 'Número de lotes no coincide'}
            
            # Actualizar el orden de cada lote usando auth_user_id
            for index, lote_id in enumerate(nuevo_orden, 1):
                self.client.table('origenes_botanicos') \
                    .update({'orden_miel': index}) \
                    .eq('id', lote_id) \
                    .eq('auth_user_id', usuario_id) \
                    .execute()
            
            return {
                'success': True,
                'message': 'Lotes reordenados exitosamente'
            }
            
        except Exception as e:
            logger.error(f"Error al reordenar lotes: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def obtener_especies_por_zona(self, usuario_id: str) -> Dict[str, Any]:
        """Obtiene las especies florales según la zona geográfica del usuario con debug completo."""
        try:
            logger.info(f"=== DEBUG ESPECIES POR ZONA ===")            
            logger.info(f"🔍 Buscando especies para usuario: {usuario_id}")
            
            # 1. Obtener información de contacto del usuario
            response = self.client.table('info_contacto').select('*').eq('auth_user_id', usuario_id).execute()
            
            if not response.data or len(response.data) == 0:
                logger.warning(f"⚠️ No se encontró info_contacto para usuario {usuario_id}")
                return {
                    'success': False,
                    'message': 'Usuario no encontrado en sistema',
                    'especies': [],
                    'comuna': None
                }
            
            user_data = response.data[0]
            comuna = user_data.get('comuna')
            logger.info(f"📍 Comuna detectada: {comuna}")
            
            if not comuna:
                logger.warning(f"⚠️ Usuario {usuario_id} no tiene comuna registrada")
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
                logger.info(f"📚 Datos CSV cargados: {len(classes_data)} comunas disponibles")
                
                if comuna in classes_data:
                    # Extraer todas las especies de todas las clases para esta comuna
                    especies = []
                    for clase, especies_clase in classes_data[comuna].items():
                        especies.extend(especies_clase)
                    
                    # Remover duplicados manteniendo orden
                    especies = list(dict.fromkeys(especies))
                    logger.info(f"🌸 Especies del CSV para {comuna}: {especies}")
                    
                else:
                    logger.warning(f"⚠️ Comuna {comuna} no encontrada en CSV")
                    especies = []
                    
            except Exception as csv_error:
                logger.error(f"❌ Error al cargar CSV: {csv_error}")
                especies = []
            logger.info(f"🌸 Especies encontradas para {comuna}: {especies}")
            logger.info(f"📊 Total especies disponibles: {len(especies)}")
            
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
                logger.warning(f"⚠️ No hay especies registradas para la comuna: {comuna}")
                return {
                    'success': False,
                    'usuario_id': usuario_id,
                    'comuna': comuna,
                    'especies': [],
                    'total_especies': 0,
                    'message': f'No hay especies registradas para {comuna}'
                }
            
        except Exception as e:
            logger.error(f"❌ Error al obtener especies para usuario {usuario_id}: {str(e)}")
            return {
                'success': False,
                'message': f'Error al obtener especies: {str(e)}',
                'especies': [],
                'comuna': None
            }
    
    def _validar_datos_lote(self, datos: Dict[str, Any]) -> List[str]:
        """Valida los datos del lote."""
        errores = []
        
        # Validar nombre
        if not datos.get('nombre_miel') or len(datos['nombre_miel'].strip()) < 2:
            errores.append("El nombre de la miel debe tener al menos 2 caracteres")
        
        # Validar temporadas
        temporadas = datos.get('temporadas', '')
        if not temporadas:
            errores.append("Debe seleccionar al menos una temporada")
        else:
            # Validar que las temporadas sean nombres válidos separados por guiones
            temporadas_validas = ['VERANO', 'OTONO', 'INVIERNO', 'PRIMAVERA']
            temporadas_list = [t.strip() for t in temporadas.split(' - ')]
            
            for temporada in temporadas_list:
                if temporada not in temporadas_validas:
                    errores.append(f"Temporada inválida: {temporada}")
        
        # Validar kilos producidos
        try:
            kg_producidos = float(datos.get('kg_producidos', 0))
            if kg_producidos < 0:
                errores.append("Los kilos producidos deben ser mayores o iguales a 0")
        except (ValueError, TypeError):
            errores.append("Los kilos producidos deben ser un número válido")
        
        # Validar composición polínica
        composicion = datos.get('composicion_polen', {})
        if isinstance(composicion, dict):
            # Validar que todos los valores sean números válidos entre 0 y 100
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
            if not composicion:
                errores.append("La composición polínica no puede estar vacía si se proporciona")
        
        return errores
    
    def _reordenar_lotes(self, usuario_id: str, orden_eliminado: int) -> None:
        """Reordena los lotes después de eliminar uno."""
        try:
            # Obtener lotes con orden mayor al eliminado usando auth_user_id
            lotes_posteriores = self.client.table('origenes_botanicos') \
                .select('id, orden_miel') \
                .eq('auth_user_id', usuario_id) \
                .gt('orden_miel', orden_eliminado) \
                .execute()
            
            # Decrementar el orden de cada lote posterior
            for lote in lotes_posteriores.data:
                nuevo_orden = lote['orden_miel'] - 1
                self.client.table('origenes_botanicos') \
                    .update({'orden_miel': nuevo_orden}) \
                    .eq('id', lote['id']) \
                    .execute()
                    
        except Exception as e:
            logger.error(f"Error al reordenar lotes: {str(e)}")

# Instancia global
from supabase_client import db
lotes_manager = LotesManager(db.client)
