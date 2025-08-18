"""
Módulo para gestionar lotes de miel con control de orden secuencial.
"""
import uuid
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class LotesManager:
    """Gestiona la creación, edición y reordenamiento de lotes de miel."""
    
    def __init__(self, supabase_client):
        """Inicializa con cliente Supabase."""
        self.client = supabase_client
    
    def obtener_lotes_usuario(self, usuario_id: str) -> List[Dict[str, Any]]:
        """Obtiene todos los lotes de miel de un usuario ordenados por orden_miel."""
        try:
            response = self.client.rpc('obtener_lotes_usuario_func', {
                'p_usuario_id': usuario_id
            }).execute()
            
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
            
            # Preparar datos para insertar directamente en la tabla
            composicion_polen = datos.get('composicion_polen', {})
            
            # Asegurar que composicion_polen sea un objeto JSON válido
            if isinstance(composicion_polen, str):
                try:
                    composicion_polen = json.loads(composicion_polen)
                except json.JSONDecodeError:
                    composicion_polen = {}
            elif not isinstance(composicion_polen, dict):
                composicion_polen = {}
            
            datos_lote = {
                'usuario_id': usuario_id,
                'nombre_miel': datos['nombre_miel'],
                'temporada': f"{datos['temporada']}-{datos['anio']}",
                'kg_producidos': float(datos['kg_producidos']),
                'orden_miel': siguiente_orden,
                'composicion_polen': composicion_polen
            }
            
            logger.info(f"Datos a insertar: {json.dumps(datos_lote, indent=2)}")
            
            response = self.client.table('origenes_botanicos').insert(datos_lote).execute()

            logger.info(f"Respuesta de Supabase: {response.data}")
            
            if response.data and len(response.data) > 0:
                lote_data = response.data[0]
                # Manejar diferentes estructuras de respuesta
                lote_id = lote_data.get('lote_id') or lote_data.get('id')
                orden = lote_data.get('nuevo_orden') or lote_data.get('orden_miel')
                
                return {
                    'success': True,
                    'lote': {
                        'id': lote_id,
                        'usuario_id': usuario_id,
                        'nombre_miel': datos['nombre_miel'],
                        'temporada': datos['temporada'],
                        'anio': int(datos['anio']),
                        'kg_producidos': datos['kg_producidos'],
                        'orden_miel': orden
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
            # Verificar que el lote pertenece al usuario
            lote_actual = self.client.table('origenes_botanicos') \
                .select('*') \
                .eq('id', lote_id) \
                .eq('usuario_id', usuario_id) \
                .single() \
                .execute()
            
            if not lote_actual.data:
                return {'success': False, 'error': 'Lote no encontrado'}
            
            # Validar datos
            errores = self._validar_datos_lote(datos)
            if errores:
                return {'success': False, 'error': '; '.join(errores)}
            
            # Preparar datos para actualizar
            datos_actualizar = {
                'nombre_miel': datos['nombre_miel'].strip(),
                'temporada': f"{datos['temporada']}-{datos['anio']}",
                'kg_producidos': float(datos['kg_producidos']),
                'composicion_polen': json.dumps(datos.get('composicion_polen', {}))
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
            
            # Actualizar el orden de cada lote
            for index, lote_id in enumerate(nuevo_orden, 1):
                self.client.table('origenes_botanicos') \
                    .update({'orden_miel': index}) \
                    .eq('id', lote_id) \
                    .eq('usuario_id', usuario_id) \
                    .execute()
            
            return {
                'success': True,
                'message': 'Lotes reordenados exitosamente'
            }
            
        except Exception as e:
            logger.error(f"Error al reordenar lotes: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def obtener_especies_por_zona(self, usuario_id: str) -> List[str]:
        """Obtiene las especies florales según la zona geográfica del usuario."""
        try:
            # Por ahora retornar lista básica, luego se puede personalizar por zona
            especies_base = [
                'Ulmo',
                'Quillay',
                'Eucalipto',
                'Tiaca',
                'Lingue',
                'Avellano',
                'Maitén',
                'Raulí',
                'Roble',
                'Flores Silvestres',
                'Mielato',
                'Otros'
            ]
            return especies_base
            
        except Exception as e:
            logger.error(f"Error al obtener especies: {str(e)}")
            return []
    
    def _validar_datos_lote(self, datos: Dict[str, Any]) -> List[str]:
        """Valida los datos del lote."""
        errores = []
        
        # Validar nombre
        if not datos.get('nombre_miel') or len(datos['nombre_miel'].strip()) < 2:
            errores.append("El nombre de la miel debe tener al menos 2 caracteres")
        
        # Validar temporada
        if not datos.get('temporada') or datos['temporada'] not in ['1', '2', '3', '4']:
            errores.append("Debe seleccionar una temporada válida")
        
        # Validar año
        if not datos.get('anio') or not str(datos['anio']).isdigit():
            errores.append("Debe seleccionar un año válido")
        
        # Validar kilos
        try:
            kg = float(datos['kg_producidos'])
            if kg < 0:
                errores.append("Los kilos producidos deben ser mayores o iguales a 0")
        except (ValueError, TypeError):
            errores.append("Los kilos producidos deben ser un número válido")
        
        # Validar composición polínica
        composicion = datos.get('composicion_polen', {})
        if isinstance(composicion, dict):
            total = sum(float(v) for v in composicion.values() if str(v).replace('.', '').isdigit())
            if total > 100:
                errores.append("La suma de porcentajes de polen no puede exceder 100%")
        
        return errores
    
    def _reordenar_lotes(self, usuario_id: str, orden_eliminado: int) -> None:
        """Reordena los lotes después de eliminar uno."""
        try:
            # Obtener lotes con orden mayor al eliminado
            lotes_posteriores = self.client.table('origenes_botanicos') \
                .select('id, orden_miel') \
                .eq('usuario_id', usuario_id) \
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
