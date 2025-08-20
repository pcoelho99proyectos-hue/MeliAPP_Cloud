"""
Módulo de rutas para gestión de lotes de miel en MeliAPP_v2.

Este módulo contiene las rutas relacionadas con:
- Gestión de lotes de miel (API y web)
- Invocación de Edge Functions para lotes
- Páginas web para gestionar lotes
"""

import logging
import json
from flask import Blueprint, request, jsonify, render_template, session, flash, redirect, url_for, g
from supabase_client import SupabaseClient
from auth_manager import AuthManager
from lotes_manager import lotes_manager
from modify_DB import DatabaseModifier
from datetime import datetime

db_client = SupabaseClient()
logger = logging.getLogger(__name__)

# Crear blueprints para rutas de lotes
lotes_api_bp = Blueprint('lotes_api', __name__, url_prefix='/api')
lotes_web_bp = Blueprint('lotes_web', __name__)
lotes_debug_bp = Blueprint('lotes_debug', __name__, url_prefix='/debug')

@lotes_api_bp.route('/lote/<lote_id>', methods=['GET'])
def obtener_lote(lote_id):
    """
    Endpoint para obtener un lote específico por ID.
    
    GET /api/lote/<lote_id>
    """
    try:
        logger.info(f"Obteniendo lote con ID: {lote_id}")
        
        # Usar DatabaseModifier para obtener un cliente autenticado
        # ya que los clientes normales pueden tener limitaciones de RLS
        db_modifier_instance = DatabaseModifier()
        auth_client = db_modifier_instance.get_authenticated_client()
        
        if not auth_client:
            logger.error("No se pudo obtener cliente autenticado para obtener lote")
            return jsonify({
                'success': False,
                'error': 'Error de autenticación'
            }), 401
            
        # Realizar la consulta con el cliente autenticado
        response = auth_client.table('origenes_botanicos').select('*').eq('id', lote_id).execute()
        
        if response.data and len(response.data) > 0:
            lote = response.data[0]
            logger.info(f"Lote encontrado: {lote.get('nombre_miel', 'Sin nombre')}, orden: {lote.get('orden_miel', 'N/A')}")
            return jsonify({
                'success': True,
                'data': lote
            })
        else:
            logger.warning(f"Lote con ID {lote_id} no encontrado en la base de datos")
            return jsonify({
                'success': False,
                'error': 'Lote no encontrado'
            }), 404
            
    except Exception as e:
        logger.error(f"Error al obtener lote {lote_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500

@lotes_api_bp.route('/lote/<lote_id>', methods=['PUT'])
@AuthManager.login_required
def actualizar_lote(lote_id):
    """
    Endpoint para actualizar un lote existente usando lotes_manager.
    
    PUT /api/lote/<lote_id>
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No se proporcionaron datos."}), 400

        # El usuario autenticado se obtiene de g.user
        auth_user_id = g.user.get('id')
        if not auth_user_id:
            return jsonify({"success": False, "error": "Usuario no autenticado."}), 401
        
        # Usar lotes_manager para la actualización centralizada
        resultado = lotes_manager.actualizar_lote(lote_id, auth_user_id, data)
        
        if resultado.get('success'):
            return jsonify(resultado), 200
        else:
            error_msg = resultado.get('error', 'Error desconocido al actualizar el lote')
            logger.error(f"Error al actualizar lote {lote_id}: {error_msg}")
            return jsonify({"success": False, "error": error_msg}), 400
            
    except Exception as e:
        logger.error(f"Excepción al actualizar lote {lote_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error inesperado en el servidor.'
        }), 500

@lotes_api_bp.route('/lote/<lote_id>', methods=['DELETE'])
@AuthManager.login_required
def eliminar_lote_route(lote_id):
    """Elimina un lote de miel de forma segura usando la sesión del usuario."""
    try:
        # Obtener el usuario_id desde la sesión de Flask (g.user)
        usuario_id = g.user.get('id')
        if not usuario_id:
            return jsonify({"success": False, "error": "Usuario no autenticado o sesión inválida"}), 401

        # Llamar al manager con el usuario_id de la sesión
        resultado = lotes_manager.eliminar_lote(lote_id, usuario_id)
        
        # Siempre devolver 200 OK si la operación se procesó correctamente,
        # incluso si no se encontró el lote para eliminar
        return jsonify(resultado), 200

    except Exception as e:
        logger.error(f"Excepción en la ruta de eliminación del lote {lote_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Ocurrió un error inesperado en el servidor."}), 500

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
        return jsonify({"success": True, "lotes": lotes})
        
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
    Endpoint para crear un lote de miel. 
    Utiliza lotes_manager para centralizar la lógica de creación.
    
    POST /api/gestionar-lote
    Body JSON: {usuario_id, temporadas, kg_producidos, fecha_registro, ...}
    """
    try:
        datos_lote = request.get_json()
        if not datos_lote:
            return jsonify({"success": False, "error": "No se proporcionaron datos."}), 400

        # El usuario autenticado se obtiene de g.user
        auth_user_id = g.user.get('id')
        if not auth_user_id:
            return jsonify({"success": False, "error": "Usuario no autenticado."}), 401
        
        # Asignar el ID de usuario autenticado a los datos del lote
        datos_lote['auth_user_id'] = auth_user_id

        # Llamar al manager para crear el lote
        resultado = lotes_manager.crear_lote(datos_lote)

        if resultado.get('success'):
            return jsonify(resultado), 201  # 201 Created
        else:
            error_msg = resultado.get('error', 'Error desconocido al crear el lote')
            logger.error(f"Fallo al crear lote para el usuario {auth_user_id}: {error_msg}")
            return jsonify({"success": False, "error": error_msg}), 400

    except Exception as e:
        logger.error(f"Excepción en la ruta de creación de lote: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Ocurrió un error inesperado en el servidor."}), 500

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

@lotes_web_bp.route('/gestionar-lotes')
@AuthManager.login_required
def gestionar_lotes_pagina():
    """Página para gestionar lotes de miel."""
    return render_template('pages/gestionar_lote.html')

# === ENDPOINTS DE DEPURACIÓN ===
@lotes_debug_bp.route('/eliminar-lote-directo/<lote_id>', methods=['GET'])
def debug_eliminar_lote_directo(lote_id):
    """Endpoint de depuración para eliminar un lote directamente por su ID."""
    try:
        # Obtener información del lote antes de eliminarlo
        logger.info(f"DEBUG: Intentando eliminar lote {lote_id} directamente")
        
        lote_info = db_client.client.table('origenes_botanicos') \
            .select('id, nombre_miel, auth_user_id, orden_miel, temporada') \
            .eq('id', lote_id) \
            .single() \
            .execute()
            
        if not lote_info.data:
            return jsonify({"success": False, "error": "Lote no encontrado"}), 404
            
        lote_data = lote_info.data
        logger.info(f"DEBUG: Información del lote a eliminar: {lote_data}")
        
        # Obtener el auth_user_id del lote
        auth_user_id = lote_data.get('auth_user_id')
        if not auth_user_id:
            return jsonify({"success": False, "error": "Lote sin usuario asociado"}), 400
        
        # Intentar eliminar usando db_modifier directamente
        from modify_DB import db_modifier
        resultado, status_code = db_modifier.delete_record(
            table='origenes_botanicos',
            extra_conditions={'id': lote_id},
            user_uuid=auth_user_id
        )
        
        logger.info(f"DEBUG: Resultado de eliminar con db_modifier: {resultado} (status: {status_code})")
        
        # Si falló, intentar con una eliminación directa
        if not resultado.get('success'):
            logger.warning(f"DEBUG: Fallando con db_modifier, intentando eliminación directa...")
            
            # Obtener cliente autenticado
            auth_client = db_modifier.get_authenticated_client()
            if not auth_client:
                return jsonify({"success": False, "error": "No se pudo obtener cliente autenticado"}), 401
                
            # Eliminación directa
            delete_result = auth_client.table('origenes_botanicos').delete().eq('id', lote_id).execute()
            
            logger.info(f"DEBUG: Resultado de eliminación directa: {delete_result.data}")
            
            if hasattr(delete_result, 'error') and delete_result.error:
                return jsonify({"success": False, "error": f"Error en eliminación directa: {delete_result.error}"}), 500
                
            return jsonify({
                "success": True,
                "message": "Lote eliminado correctamente mediante eliminación directa",
                "lote": lote_data,
                "deleted": delete_result.data
            })
            
        return jsonify({
            "success": resultado.get('success', False),
            "message": resultado.get('message', 'Sin mensaje'),
            "deleted_count": resultado.get('deleted_count', 0),
            "lote": lote_data
        }), status_code
        
    except Exception as e:
        logger.error(f"DEBUG: Error en el endpoint de debug: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500
