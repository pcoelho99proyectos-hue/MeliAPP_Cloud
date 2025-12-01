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
from auth_manager import AuthManager
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

@search_bp.route('/profile/me', methods=['GET'])
def get_my_profile_complete():
    """
    NUEVO endpoint API REST para Flutter.
    Obtiene datos COMPLETOS del usuario autenticado: usuarios + info_contacto.
    Usa el MISMO método que /profile (searcher.get_user_profile_data)
    
    GET /api/profile/me
    
    Returns:
        JSON con todos los datos de usuarios + info_contacto
    """
    try:
        # Verificar autenticación
        if 'user_id' not in session:
            return jsonify({"success": False, "error": "Usuario no autenticado"}), 401
        
        current_user_id = session['user_id']
        logger.info(f"[API /profile/me] Obteniendo datos completos para: {current_user_id}")
        
        # Usar el MISMO método que usa /profile para obtener datos completos
        profile_data = searcher.get_user_profile_data(current_user_id)
        
        if not profile_data:
            logger.warning(f"[API /profile/me] Usuario no encontrado: {current_user_id}")
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
        
        # Combinar datos de usuario e info_contacto en un solo objeto
        user_data = profile_data.get('user') or {}
        contact_data = profile_data.get('contact_info') or {}
        
        # Crear objeto completo combinando ambas tablas
        complete_user = {
            **user_data,  # Todos los campos de usuarios
            'nombre_completo': contact_data.get('nombre_completo'),
            'nombre_empresa': contact_data.get('nombre_empresa'),
            'correo_principal': contact_data.get('correo_principal'),
            'telefono_principal': contact_data.get('telefono_principal'),
            'direccion': contact_data.get('direccion'),
            'comuna': contact_data.get('comuna'),
            'region': contact_data.get('region'),
        }
        
        logger.info(f"[API /profile/me] Datos completos obtenidos exitosamente")
        
        return jsonify({
            "success": True,
            "user_id": current_user_id,
            "user": complete_user
        })
        
    except Exception as e:
        logger.error(f"[API /profile/me] Error: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@search_bp.route('/profile/<user_id>', methods=['GET'])
def get_user_profile_by_id(user_id):
    """
    Endpoint API REST para Flutter - Obtiene perfil público de cualquier usuario.
    
    Permite a usuarios autenticados consultar información de contacto de otros usuarios
    para facilitar la comunicación entre apicultores, proveedores y compradores.
    
    GET /api/profile/{user_id}
    
    Args:
        user_id: auth_user_id del usuario a consultar (UUID completo o segmento de 8 chars)
    
    Returns:
        JSON con datos públicos: nombre, empresa, email, teléfono, ubicación
        
    Example response:
        {
            "auth_user_id": "uuid",
            "username": "rodrigojc",
            "nombre_completo": "Rodrigo Jofré",
            "nombre_empresa": "Honey CORPs",
            "correo_principal": "email@example.com",
            "telefono_principal": "+56 9 666 777 88",
            "comuna": "Hornopiren",
            "region": "Los Lagos",
            "role": "PROVEEDOR"
        }
    """
    try:
        logger.info(f"[API /profile/{user_id}] Consulta de perfil público")
        
        # Si es segmento de 8 chars, buscar UUID completo
        if len(user_id) == 8:
            logger.info(f"[API /profile] Buscando UUID completo para segmento: {user_id}")
            response = db.client.table('usuarios')\
                .select('auth_user_id')\
                .execute()
            
            full_uuid = None
            for user in response.data:
                if user['auth_user_id'].startswith(user_id):
                    full_uuid = user['auth_user_id']
                    break
            
            if not full_uuid:
                return jsonify({"error": "Usuario no encontrado"}), 404
            
            user_id = full_uuid
        
        # Obtener datos completos del usuario usando método centralizado
        profile_data = searcher.get_user_profile_data(user_id)
        
        if not profile_data:
            logger.warning(f"[API /profile/{user_id}] Usuario no encontrado")
            return jsonify({"error": "Usuario no encontrado"}), 404
        
        # Extraer datos de usuario y contacto
        user_data = profile_data.get('user') or {}
        contact_data = profile_data.get('contact_info') or {}
        
        # Crear respuesta con datos públicos esenciales
        public_profile = {
            # Identificación
            'auth_user_id': user_id,
            'id': user_id,  # Alias para compatibilidad
            'username': user_data.get('username'),
            'role': user_data.get('role'),
            'tipo_usuario': user_data.get('tipo_usuario'),
            'status': user_data.get('status'),
            
            # Información de contacto pública
            'nombre_completo': contact_data.get('nombre_completo'),
            'nombre_empresa': contact_data.get('nombre_empresa'),
            'correo_principal': contact_data.get('correo_principal'),
            'email': contact_data.get('correo_principal'),  # Alias
            'telefono_principal': contact_data.get('telefono_principal'),
            'telefono': contact_data.get('telefono_principal'),  # Alias
            
            # Ubicación
            'comuna': contact_data.get('comuna'),
            'region': contact_data.get('region'),
            'direccion': contact_data.get('direccion'),
        }
        
        logger.info(f"[API /profile/{user_id}] Perfil público obtenido exitosamente")
        return jsonify(public_profile)
        
    except Exception as e:
        logger.error(f"[API /profile/{user_id}] Error: {str(e)}")
        return jsonify({"error": "Error al obtener perfil"}), 500

@search_bp.route('/usuario/<uuid_segment>/qr', methods=['GET'])
@AuthManager.login_required
def get_user_qr(uuid_segment):
    """
    Genera y devuelve un código QR que redirecciona al perfil del usuario.
    
    GET /api/usuario/550e8400/qr?format=png -> Devuelve una imagen PNG del QR
    GET /api/usuario/550e8400/qr?format=svg -> Devuelve una imagen SVG del QR
    GET /api/usuario/550e8400/qr?format=json -> Devuelve un JSON con el QR en base64
    """
    try:
        # Verificar que el usuario solo puede generar QR de su propio perfil
        current_user_id = AuthManager.get_current_user_id()
        if not current_user_id:
            return jsonify({"error": "Usuario no autenticado"}), 401
            
        if len(uuid_segment) != 8:
            return jsonify({"error": "El segmento UUID debe tener 8 caracteres"}), 400
            
        # Verificar que el segmento UUID corresponde al usuario autenticado
        if not str(current_user_id).startswith(uuid_segment):
            return jsonify({"error": "No tienes permisos para generar este QR"}), 403
            
        # Usar el ID del usuario autenticado
        user_id = current_user_id
        
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
        logger.info(f"[DEBUG /buscar] Término de búsqueda recibido: '{search_term}'")
        
        if search_term:
            try:
                # Primero buscar por nombre_completo en info_contacto (mismo método que las sugerencias)
                logger.info(f"[DEBUG /buscar] Buscando por nombre_completo en info_contacto")
                
                # Buscar por coincidencia exacta (sin espacios extra)
                try:
                    contact_response = db.client.table('info_contacto') \
                        .select('auth_user_id, nombre_completo') \
                        .eq('nombre_completo', search_term) \
                        .limit(1) \
                        .execute()
                    
                    if contact_response.data:
                        user_uuid = contact_response.data[0]['auth_user_id']
                        logger.info(f"[DEBUG /buscar] Usuario encontrado por nombre_completo exacto: {user_uuid}")
                        return redirect(url_for('profile.profile', user_id=user_uuid))
                except Exception as exact_error:
                    logger.info(f"[DEBUG /buscar] Búsqueda exacta falló: {str(exact_error)}")
                
                # Buscar ignorando espacios al inicio y final
                try:
                    trimmed_response = db.client.table('info_contacto') \
                        .select('auth_user_id, nombre_completo') \
                        .ilike('nombre_completo', f'{search_term.strip()}%') \
                        .limit(1) \
                        .execute()
                    
                    if trimmed_response.data:
                        # Verificar si es una coincidencia exacta (ignorando espacios)
                        found_name = trimmed_response.data[0]['nombre_completo'].strip()
                        if found_name.lower() == search_term.strip().lower():
                            user_uuid = trimmed_response.data[0]['auth_user_id']
                            logger.info(f"[DEBUG /buscar] Usuario encontrado por nombre_completo (ignorando espacios): {user_uuid}")
                            return redirect(url_for('profile.profile', user_id=user_uuid))
                except Exception as trimmed_error:
                    logger.info(f"[DEBUG /buscar] Búsqueda con trim falló: {str(trimmed_error)}")
                
                # Si no se encuentra por nombre exacto, buscar por identificador tradicional
                logger.info(f"[DEBUG /buscar] Buscando por identificador tradicional")
                user_info = searcher.find_user_by_identifier(search_term)
                
                if user_info:
                    user_uuid = user_info['auth_user_id']
                    logger.info(f"[DEBUG /buscar] Usuario encontrado por identificador: {user_uuid}")
                    return redirect(url_for('profile.profile', user_id=user_uuid))
                
                # Búsqueda parcial por nombre_completo
                logger.info(f"[DEBUG /buscar] Buscando parcialmente por nombre_completo")
                partial_response = db.client.table('info_contacto') \
                    .select('auth_user_id, nombre_completo') \
                    .ilike('nombre_completo', f'%{search_term}%') \
                    .limit(1) \
                    .execute()
                
                if partial_response.data:
                    user_uuid = partial_response.data[0]['auth_user_id']
                    logger.info(f"[DEBUG /buscar] Usuario encontrado por búsqueda parcial: {user_uuid}")
                    return redirect(url_for('profile.profile', user_id=user_uuid))
                
                # Fallback: buscar por username
                logger.info(f"[DEBUG /buscar] Fallback: buscando por username")
                search_results = searcher.search_users_by_query(search_term)
                if search_results:
                    logger.info(f"[DEBUG /buscar] Encontrados {len(search_results)} resultados por username")
                    return render_template('pages/search.html', usuarios=search_results)
                
                logger.warning(f"[DEBUG /buscar] No se encontró usuario para: '{search_term}'")
                return render_template('pages/search.html', error="Usuario no encontrado")
                
            except Exception as e:
                logger.error(f"[DEBUG /buscar] Error en búsqueda: {str(e)}", exc_info=True)
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
            
        # Búsqueda principal - buscar por nombre_completo en info_contacto
        logger.info(f"[DEBUG /sugerir] Ejecutando query JOIN para obtener datos completos")
        
        try:            
            # Debug: Primero verificar que hay datos en la tabla con el cliente directo
            test_all = db.client.table('info_contacto') \
                .select('auth_user_id, nombre_completo') \
                .limit(3) \
                .execute()
            logger.info(f"[DEBUG /sugerir] Test general (cliente directo): {len(test_all.data) if test_all.data else 0} registros totales")
            if test_all.data:
                logger.info(f"[DEBUG /sugerir] Primer registro: {test_all.data[0]}")
            
            # Query con ilike usando cliente directo
            logger.info(f"[DEBUG /sugerir] Ejecutando con cliente directo: .ilike('nombre_completo', '%{termino}%')")
            response = db.client.table('info_contacto') \
                .select('auth_user_id, nombre_completo, nombre_empresa') \
                .ilike('nombre_completo', f'%{termino}%') \
                .limit(10) \
                .execute()
                
            logger.info(f"[DEBUG /sugerir] Response ilike (cliente directo): {len(response.data) if response.data else 0} resultados")
            
            contacts = response.data if hasattr(response, 'data') else []
            logger.info(f"[DEBUG /sugerir] Contactos finales encontrados: {len(contacts)}")
            
            if contacts:
                logger.info(f"[DEBUG /sugerir] Primer contacto encontrado: {contacts[0]}")
                
        except Exception as query_error:
            logger.error(f"[DEBUG /sugerir] Error en query info_contacto: {str(query_error)}")
            contacts = []
        
        # Convertir contactos a formato de usuarios para mantener compatibilidad
        users = []
        for contact in contacts:
            # Obtener tipo_usuario de la tabla usuarios usando cliente directo
            tipo_usuario = 'Usuario'
            try:
                user_response = db.client.table('usuarios') \
                    .select('tipo_usuario') \
                    .eq('auth_user_id', contact['auth_user_id']) \
                    .single() \
                    .execute()
                if user_response.data:
                    tipo_usuario = user_response.data.get('tipo_usuario', 'Usuario')
            except:
                pass  # Usar valor por defecto si no se encuentra
            
            users.append({
                'auth_user_id': contact['auth_user_id'],
                'username': contact['nombre_completo'],  # Usar nombre_completo como username para compatibilidad
                'tipo_usuario': tipo_usuario,
                'status': 'active'
            })
        
        logger.info(f"[DEBUG /sugerir] Usuarios procesados: {len(users)}")
        
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
