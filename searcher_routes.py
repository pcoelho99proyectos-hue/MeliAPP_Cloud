"""
Módulo de rutas para operaciones de búsqueda usando Searcher en MeliAPP_v2.

Este módulo contiene las rutas relacionadas con:
- Búsqueda de usuarios
- Sugerencias de autocompletado
- Operaciones que utilizan la clase Searcher
"""

import logging
import io
import base64
from flask import Blueprint, render_template, request, jsonify, url_for, redirect, send_file, session
from supabase_client import db
from searcher import Searcher
import segno

logger = logging.getLogger(__name__)

# Crear blueprints para rutas de búsqueda
search_bp = Blueprint('search', __name__, url_prefix='/api')
search_web_bp = Blueprint('search_web', __name__)

# Inicializar componentes
searcher = Searcher(db.client)

# ====================
# Rutas API de Búsqueda
# ====================

@search_bp.route('/usuario/<uuid_segment>', methods=['GET'])
def get_usuario_by_uuid_segment(uuid_segment):
    """
    Redirige al perfil del usuario usando el primer segmento de su UUID.
    
    GET /api/usuario/550e8400 -> redirige al perfil del usuario con ID que comience con 550e8400
    """
    try:
        if len(uuid_segment) != 8:
            return jsonify({"error": "El segmento UUID debe tener 8 caracteres"}), 400
            
        # Buscar usuarios y filtrar por segmento UUID en Python
        response = db.client.table('usuarios')\
            .select('auth_user_id')\
            .execute()
            
        if not response.data:
            return jsonify({"error": "No hay usuarios en la base de datos"}), 404
            
        # Filtrar usuarios cuyo ID comience con el segmento
        matching_users = [user for user in response.data if str(user['auth_user_id']).startswith(uuid_segment)]
            
        if not matching_users:
            return jsonify({"error": "Usuario no encontrado"}), 404
            
        # Retornar información del usuario encontrado
        user_id = matching_users[0]['auth_user_id']
        return jsonify({
            "success": True,
            "user_id": user_id,
            "profile_url": f"/profile/{user_id}"
        })
            
    except Exception as e:
        logger.error(f"Error al buscar usuario por segmento UUID: {str(e)}")
        return jsonify({"error": "Error interno del servidor"}), 500

@search_bp.route('/user/current', methods=['GET'])
def get_current_user():
    """
    Obtiene el ID del usuario actual usando la misma lógica que searcher.get_user_id_by_auth_id.
    
    GET /api/user/current
    """
    try:
        # Verificar si hay usuario autenticado
        if 'user_id' not in session:
            return jsonify({"success": False, "error": "Usuario no autenticado"}), 401
            
        # Obtener el ID del usuario actual desde la sesión
        current_user_id = session['user_id']
        
        # Verificar que el usuario existe usando SupabaseClient
        user_response = db.get_usuario(current_user_id)
            
        if not user_response.data:
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
            
        return jsonify({
            "success": True,
            "user_id": current_user_id,
            "user": user_response.data
        })
        
    except Exception as e:
        logger.error(f"Error al obtener usuario actual: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@search_bp.route('/usuario/<uuid_segment>/qr', methods=['GET'])
def get_user_qr(uuid_segment):
    """
    Genera y devuelve un código QR que redirecciona al perfil del usuario.
    
    GET /api/usuario/550e8400/qr?format=png -> Devuelve una imagen PNG del QR
    GET /api/usuario/550e8400/qr?format=svg -> Devuelve una imagen SVG del QR
    GET /api/usuario/550e8400/qr?format=json -> Devuelve un JSON con el QR en base64
    """
    try:
        if len(uuid_segment) != 8:
            return jsonify({"error": "El segmento UUID debe tener 8 caracteres"}), 400
            
        # Buscar usuarios cuyo UUID comience con el segmento proporcionado
        response = db.client.table('usuarios')\
            .select('auth_user_id')\
            .execute()
            
        if not response.data:
            return jsonify({"error": "No hay usuarios en la base de datos"}), 404
            
        # Filtrar usuarios cuyo ID comience con el segmento
        matching_users = [user for user in response.data if str(user['auth_user_id']).startswith(uuid_segment)]
            
        if not matching_users:
            return jsonify({"error": "Usuario no encontrado"}), 404
            
        # Usar el primer usuario que coincida
        user_id = matching_users[0]['auth_user_id']
        
        qr_format = request.args.get('format', 'png').lower()
        scale = int(request.args.get('scale', 10))
        
        # Generar URL del perfil
        profile_url = url_for('profile.profile', user_id=user_id, _external=True)
        qr = segno.make(profile_url)
        
        if qr_format == 'png':
            output = io.BytesIO()
            qr.save(output, kind='png', scale=scale)
            output.seek(0)
            return send_file(output, mimetype='image/png', as_attachment=False, download_name=f'qr-{user_id}.png')
        
        elif qr_format == 'json':
            output = io.BytesIO()
            qr.save(output, kind='png', scale=scale)
            qr_base64 = base64.b64encode(output.getvalue()).decode('ascii')
            
            return jsonify({
                "success": True,
                "qr_code": f"data:image/png;base64,{qr_base64}",
                "user_id": user_id,
                "uuid_segment": uuid_segment
            })
        else:
            return jsonify({"error": f"Formato '{qr_format}' no soportado. Formatos válidos: png, json"}), 400
            
    except Exception as e:
        logger.error(f"Error al generar QR para usuario con segmento UUID {uuid_segment}: {str(e)}", exc_info=True)
        return jsonify({"error": "Error interno del servidor"}), 500

# ====================
# Rutas Web de Búsqueda
# ====================

@search_web_bp.route('/search')
def search():
    """
    Página de búsqueda con el nuevo template.
    
    GET /search
    """
    return render_template('pages/search.html')

@search_web_bp.route('/buscar', methods=['GET', 'POST'])
def buscar():
    """
    Ruta de búsqueda que maneja búsquedas por nombre o ID.
    """
    if request.method == 'POST':
        search_term = request.form.get('usuario_id', '').strip()
        if search_term:
            try:
                # Buscar usuario por identificador usando función centralizada
                user_info = searcher.find_user_by_identifier(search_term)
                
                if user_info:
                    user_uuid = user_info['auth_user_id']
                    return redirect(url_for('profile.profile', user_id=user_uuid))
                else:
                    # También buscar por nombre/username
                    search_results = searcher.search_users_by_query(search_term)
                    if search_results:
                        return render_template('pages/search.html', 
                                           usuarios=search_results)
                    return render_template('pages/search.html', 
                                         error="Usuario no encontrado")
            except Exception as e:
                logger.error(f"Error en búsqueda: {str(e)}")
                return render_template('pages/search.html', error="Error al buscar usuario")
    
    return redirect(url_for('search_web.search'))

@search_web_bp.route('/sugerir', methods=['GET'])
def sugerir():
    """
    Endpoint para obtener sugerencias de autocompletado de usuarios.
    
    GET /sugerir?q=<término>
    """
    try:
        termino = request.args.get('q', '').strip()
        logger.info(f"[DEBUG /sugerir] Término recibido: '{termino}'")
        
        if not termino:
            logger.info("[DEBUG /sugerir] Término vacío, retornando lista vacía")
            return jsonify({'suggestions': []})
        
        if len(termino) < 2:
            logger.info(f"[DEBUG /sugerir] Término muy corto ({len(termino)} chars), retornando lista vacía")
            return jsonify({'suggestions': []})
            
        logger.info(f"[DEBUG /sugerir] Iniciando búsqueda en tabla usuarios con término: '{termino}'")
        
        # Test de conexión a BD
        try:
            test_response = searcher.supabase.table('usuarios').select('auth_user_id').limit(1).execute()
            logger.info(f"[DEBUG /sugerir] Test de conexión BD exitoso. Datos disponibles: {bool(test_response.data)}")
            logger.info(f"[DEBUG /sugerir] Número de registros en test: {len(test_response.data) if test_response.data else 0}")
            
            # Test adicional: verificar auth.users
            try:
                auth_test = searcher.supabase.table('auth.users').select('id').limit(1).execute()
                logger.info(f"[DEBUG /sugerir] Registros en auth.users: {len(auth_test.data) if auth_test.data else 0}")
            except Exception as auth_error:
                logger.info(f"[DEBUG /sugerir] No se puede acceder a auth.users: {str(auth_error)}")
            
            # Test de estructura de tabla
            if test_response.data and len(test_response.data) > 0:
                logger.info(f"[DEBUG /sugerir] Estructura primer registro: {test_response.data[0].keys()}")
            else:
                logger.warning("[DEBUG /sugerir] PROBLEMA: La tabla usuarios está VACÍA")
                # Intentar buscar en info_contacto como alternativa
                try:
                    info_test = searcher.supabase.table('info_contacto').select('auth_user_id, nombre_completo').limit(5).execute()
                    logger.info(f"[DEBUG /sugerir] Registros en info_contacto: {len(info_test.data) if info_test.data else 0}")
                    if info_test.data:
                        logger.info(f"[DEBUG /sugerir] Primer registro info_contacto: {info_test.data[0]}")
                except Exception as info_error:
                    logger.info(f"[DEBUG /sugerir] Error accediendo info_contacto: {str(info_error)}")
                
        except Exception as conn_error:
            logger.error(f"[DEBUG /sugerir] Error de conexión BD: {str(conn_error)}")
            return jsonify({"error": "Error de conexión a base de datos"}), 500
            
        # Búsqueda principal - intentar usuarios primero
        logger.info(f"[DEBUG /sugerir] Ejecutando query: usuarios.select('auth_user_id, username, tipo_usuario, status').ilike('username', '%{termino}%').limit(10)")
        
        response = searcher.supabase.table('usuarios') \
            .select('auth_user_id, username, tipo_usuario, status') \
            .ilike('username', f'%{termino}%') \
            .limit(10) \
            .execute()
            
        logger.info(f"[DEBUG /sugerir] Response recibido. Tipo: {type(response)}")
        logger.info(f"[DEBUG /sugerir] Response.data existe: {hasattr(response, 'data')}")
        
        users = response.data if hasattr(response, 'data') else []
        logger.info(f"[DEBUG /sugerir] Usuarios encontrados: {len(users)}")
        
        # Si no hay usuarios, buscar en info_contacto como fallback
        if not users:
            logger.info(f"[DEBUG /sugerir] No hay usuarios, buscando en info_contacto...")
            try:
                info_response = searcher.supabase.table('info_contacto') \
                    .select('auth_user_id, nombre_completo, nombre_empresa') \
                    .ilike('nombre_completo', f'%{termino}%') \
                    .limit(10) \
                    .execute()
                
                if info_response.data:
                    logger.info(f"[DEBUG /sugerir] Encontrados {len(info_response.data)} registros en info_contacto")
                    # Convertir info_contacto a formato de usuarios
                    for contact in info_response.data:
                        users.append({
                            'auth_user_id': contact['auth_user_id'],
                            'username': contact.get('nombre_completo', ''),
                            'tipo_usuario': 'Apicultor',
                            'status': 'active'
                        })
                else:
                    logger.info("[DEBUG /sugerir] Tampoco hay registros en info_contacto")
            except Exception as info_error:
                logger.error(f"[DEBUG /sugerir] Error buscando en info_contacto: {str(info_error)}")
        
        if users:
            logger.info(f"[DEBUG /sugerir] Primer usuario: {users[0]}")
        
        suggestions = []
        for i, user in enumerate(users):
            logger.info(f"[DEBUG /sugerir] Procesando usuario {i+1}: {user}")
            suggestion = {
                'id': user['auth_user_id'],
                'nombre': user.get('username', ''),
                'especialidad': user.get('tipo_usuario', 'Apicultor')
            }
            suggestions.append(suggestion)
            logger.info(f"[DEBUG /sugerir] Sugerencia creada: {suggestion}")
        
        logger.info(f"[DEBUG /sugerir] Total sugerencias generadas: {len(suggestions)}")
        return jsonify({'suggestions': suggestions})
        
    except Exception as e:
        logger.error(f"[DEBUG /sugerir] ERROR CRÍTICO: {str(e)}", exc_info=True)
        logger.error(f"[DEBUG /sugerir] Tipo de error: {type(e)}")
        return jsonify({"error": f"Error al obtener sugerencias: {str(e)}"}), 500
