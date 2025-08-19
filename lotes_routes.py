"""
Módulo de rutas para gestión de lotes de miel en MeliAPP_v2.

Este módulo contiene las rutas relacionadas con:
- Gestión de lotes de miel (API y web)
- Invocación de Edge Functions para lotes
- Páginas web para gestionar lotes
"""

import logging
import json
from flask import Blueprint, render_template, request, jsonify
from supabase_client import db
from auth_manager import AuthManager
from lotes_manager import lotes_manager
from modify_DB import DatabaseModifier
from datetime import datetime

logger = logging.getLogger(__name__)

# Crear blueprints para rutas de lotes
lotes_api_bp = Blueprint('lotes_api', __name__, url_prefix='/api')
lotes_web_bp = Blueprint('lotes_web', __name__)

@lotes_api_bp.route('/lotes/<usuario_id>', methods=['GET'])
def obtener_lotes_usuario(usuario_id):
    """
    Endpoint para obtener todos los lotes de un usuario.
    
    GET /api/lotes/<usuario_id>
    """
    logger.info(f"📦 Obteniendo lotes para usuario: {usuario_id}")
    
    try:
        lotes = lotes_manager.obtener_lotes_usuario(usuario_id)
        logger.info(f"📊 Lotes encontrados: {len(lotes)}")
        
        return jsonify({
            'success': True,
            'lotes': lotes,
            'total': len(lotes)
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error al obtener lotes: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@lotes_api_bp.route('/gestionar-lote', methods=['POST'])
@AuthManager.login_required
def manejar_lote_de_miel():
    """
    Endpoint para crear o actualizar un lote de miel.
    Actúa como un proxy seguro a la Edge Function de Supabase 'Honey_Manage_Lots'.
    
    POST /api/gestionar-lote
    Body JSON: {usuario_id, ubicacion_id, temporada, kg_producidos, ...}
    """
    try:
        datos_lote = request.get_json()
        
        if not datos_lote:
            return jsonify({
                "success": False, 
                "error": "No se proporcionaron datos en la solicitud."
            }), 400

        campos_requeridos = ['usuario_id', 'temporadas', 'kg_producidos', 'fecha_registro']
        for campo in campos_requeridos:
            if campo not in datos_lote:
                return jsonify({
                    "success": False, 
                    "error": f"Campo requerido faltante: {campo}"
                }), 400
        
        # Obtener ubicacion_id desde el perfil del usuario
        try:
            # Buscar información de contacto del usuario usando el método correcto
            user_response = db.get_contacto(datos_lote['usuario_id'])
            
            if not user_response.data:
                return jsonify({
                    "success": False,
                    "error": "Usuario no encontrado en el sistema"
                }), 400
            
            user_data = user_response.data
            ubicacion_id = user_data.get('id')  # Usar el ID del registro de info_contacto como ubicacion_id
            
            if not ubicacion_id:
                return jsonify({
                    "success": False,
                    "error": "Usuario no tiene ubicación registrada"
                }), 400
                
            # Agregar ubicacion_id a los datos
            datos_lote['ubicacion_id'] = ubicacion_id
            
        except Exception as e:
            logger.error(f"Error al obtener ubicación del usuario: {e}")
            return jsonify({
                "success": False,
                "error": f"Error al obtener ubicación del usuario: {str(e)}"
            }), 500

        # Usar DatabaseModifier para crear lote con esquema correcto
        try:
            db_modifier = DatabaseModifier()
            auth_client = db_modifier.get_authenticated_client()
            
            # Obtener el siguiente orden para el usuario
            lotes_actuales = auth_client.table('origenes_botanicos').select('*').eq('auth_user_id', datos_lote['usuario_id']).execute()
            siguiente_orden = len(lotes_actuales.data) + 1 if lotes_actuales.data else 1
            
            # Preparar datos según esquema real de origenes_botanicos
            # La fecha_registro viene del frontend en formato ISO (YYYY-MM-DD)
            # Procesar temporadas - usar el formato textual directamente
            temporada = datos_lote.get('temporadas', 'VERANO')
            
            lote_data = {
                'orden_miel': siguiente_orden,
                'nombre_miel': datos_lote['nombre_miel'],
                'temporada': temporada,  # Solo la primera temporada para cumplir con constraint
                'kg_producidos': float(datos_lote['kg_producidos']),
                'composicion_polen': datos_lote['composicion_polen'] if isinstance(datos_lote['composicion_polen'], dict) else {},
                'fecha_registro': datos_lote['fecha_registro'],  # Fecha manual en formato ISO
                'auth_user_id': datos_lote['usuario_id']
            }
            
            logger.info(f"Datos del lote a insertar: {json.dumps(lote_data, indent=2, default=str)}")
            
            # Verificar si es actualización o creación
            if 'lote_id' in datos_lote:
                # Actualizar lote existente - NO modificar fecha_registro (es inmutable)
                del lote_data['fecha_registro']  # Remover para no sobrescribir
                lote_data['fecha_actualizacion'] = datetime.now().strftime('%Y-%m-%d')
                response = auth_client.table('origenes_botanicos').update(lote_data).eq('id', datos_lote['lote_id']).execute()
            else:
                # Crear nuevo lote
                response = auth_client.table('origenes_botanicos').insert(lote_data).execute()
            
            if response.data and len(response.data) > 0:
                lote_creado = response.data[0]
                logger.info(f"Lote creado exitosamente: {lote_creado}")
                return jsonify({
                    "success": True,
                    "loteId": lote_creado.get('id'),
                    "data": {
                        "id": lote_creado.get('id'),
                        "orden": lote_creado.get('orden_miel'),
                        "nombre_miel": lote_creado.get('nombre_miel'),
                        "temporada": lote_creado.get('temporada'),
                        "kg_producidos": lote_creado.get('kg_producidos'),
                        "fecha_registro": lote_creado.get('fecha_registro')
                    }
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": "No se pudo crear/actualizar el lote"
                }), 400
                
        except Exception as e:
            logger.error(f"Error al crear/actualizar lote: {e}")
            return jsonify({
                "success": False,
                "error": f"Error al procesar el lote: {str(e)}"
            }), 500

    except ValueError as ve:
        return jsonify({
            "success": False,
            "error": f"Error de validación: {str(ve)}"
        }), 400
    except Exception as e:
        logger.error(f"Error al invocar la Edge Function Honey_Manage_Lots: {e}")
        return jsonify({
            "success": False,
            "error": f"Error interno del servidor: {str(e)}"
        }), 500

@lotes_api_bp.route('/usuario-info/<usuario_id>', methods=['GET'])
def obtener_usuario_info(usuario_id):
    """
    Endpoint para obtener información del usuario y especies disponibles por comuna.
    Usa lotes_manager para orquestar la lógica con debug completo.
    
    GET /api/usuario-info/<usuario_id>
    """
    logger.info(f"🚀 INICIANDO verificación de especies para usuario: {usuario_id}")
    
    try:
        # Usar lotes_manager para obtener especies por zona con debug completo
        resultado = lotes_manager.obtener_especies_por_zona(usuario_id)
        
        logger.info(f"📋 Resultado del lotes_manager: {resultado}")
        
        if resultado['success']:
            logger.info(f"✅ Especies encontradas exitosamente para {resultado['comuna']}")
            return jsonify(resultado), 200
        else:
            logger.warning(f"⚠️ No se pudieron obtener especies: {resultado['message']}")
            return jsonify(resultado), 404
        
    except Exception as e:
        logger.error(f"❌ Error crítico al obtener información del usuario {usuario_id}: {e}")
        return jsonify({
            'success': False,
            'message': f'Error crítico del servidor: {str(e)}',
            'usuario_id': usuario_id
        }), 500

@lotes_web_bp.route('/gestionar-lote')
@AuthManager.login_required
def gestionar_lote():
    """
    Página para gestionar lotes de miel con formulario interactivo.
    
    GET /gestionar-lote
    """
    return render_template('pages/gestionar_lote.html')
