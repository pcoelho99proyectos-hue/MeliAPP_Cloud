"""
Módulo de rutas para gestión de lotes de miel en MeliAPP_v2.

Este módulo contiene las rutas relacionadas con:
- Gestión de lotes de miel (API y web)
- Invocación de Edge Functions para lotes
- Páginas web para gestionar lotes
"""

import logging
from flask import Blueprint, render_template, request, jsonify
from supabase_client import db
from auth_manager import AuthManager
from lotes_manager import lotes_manager

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

        campos_requeridos = ['usuario_id', 'ubicacion_id', 'temporada', 'kg_producidos']
        for campo in campos_requeridos:
            if campo not in datos_lote:
                return jsonify({
                    "success": False, 
                    "error": f"Campo requerido faltante: {campo}"
                }), 400

        resultado = db.invoke_edge_function_sync('Honey_Manage_Lots', datos_lote)
        
        if 'error' in resultado:
            return jsonify({
                "success": False,
                "error": resultado.get('error', 'Error desconocido en la Edge Function')
            }), 400

        return jsonify({
            "success": True,
            "loteId": resultado.get('loteId'),
            "data": resultado
        }), 200

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
