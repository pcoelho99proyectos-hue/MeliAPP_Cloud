"""
Módulo de rutas y endpoints para la aplicación MeliAPP_v2.

Este módulo contiene todas las rutas Flask organizadas por categorías:
- Rutas de API
- Rutas web
- Rutas de autenticación (delegadas a AuthManager)
- Rutas de búsqueda
- Rutas de perfiles
- Rutas de QR
"""

import logging
import io
import base64
from flask import Blueprint, render_template, request, jsonify, url_for, redirect, send_file, session, g
from datetime import datetime
from supabase_client import db
from searcher import Searcher
from qr_code.generator import QRGenerator
from auth_manager import AuthManager
import segno

logger = logging.getLogger(__name__)

# Crear blueprints para organizar las rutas
api_bp = Blueprint('api', __name__, url_prefix='/api')
web_bp = Blueprint('web', __name__)

# Inicializar componentes
searcher = Searcher(db.client)

# ====================
# Rutas API
# ====================

@api_bp.route('/test', methods=['GET'])
def test_connection():
    """
    Prueba la conexión con la base de datos Supabase.
    
    GET /api/test
    """
    try:
        # Usar función centralizada de test desde app.py
        from app import test_database_connection
        success, message = test_database_connection()
        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route('/table/<table_name>', methods=['GET'])
def get_table_data(table_name):
    """
    Obtiene datos de una tabla específica con paginación.
    
    GET /api/table/<table_name>?page=1&per_page=20
    """
    try:
        from data_tables_supabase import get_table_data as get_table_data_func
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        success, result = get_table_data_func(table_name, page, per_page)
        
        if success:
            return jsonify({
                "success": True,
                "table": table_name,
                "data": result['data'],
                "pagination": result['pagination']
            })
        else:
            return jsonify({"success": False, "error": result}), 500
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route('/tables', methods=['GET'])
def list_tables():
    """
    Lista todas las tablas disponibles en la base de datos.
    
    GET /api/tables
    """
    try:
        from data_tables_supabase import list_tables as list_tables_func
        success, result = list_tables_func()
        if success:
            return jsonify({"success": True, "tables": result})
        else:
            return jsonify({"success": False, "error": result}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route('/gestionar-lote', methods=['POST'])
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

@api_bp.route('/test-db', methods=['GET'])
def test_db():
    """
    Prueba la conexión con la base de datos y devuelve información del sistema.
    
    GET /api/test-db
    """
    try:
        response = db.client.table('usuarios').select('auth_user_id').limit(1).execute()
        
        if response.data is not None:
            return jsonify({
                "success": True,
                "message": "Conexión exitosa con Supabase",
                "database_status": "online",
                "tables_count": len(response.data) if response.data else 0
            })
        else:
            return jsonify({
                "success": False,
                "error": "No se pudieron obtener datos de Supabase"
            }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Error de conexión: {str(e)}"
        }), 500

@api_bp.route('/usuario/<uuid_segment>', methods=['GET'])
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
        matching_users = [user for user in response.data if str(user['id']).startswith(uuid_segment)]
            
        if not matching_users:
            return jsonify({"error": "Usuario no encontrado"}), 404
            
    except Exception as e:
        logger.error(f"Error al buscar usuario por segmento UUID: {str(e)}")
        return jsonify({"error": "Error interno del servidor"}), 500

@api_bp.route('/auth/login', methods=['POST'])
def api_login():
    """
    Endpoint API para login que devuelve JSON.
    
    POST /api/auth/login
    Body JSON: {"email": "user@example.com", "password": "password"}
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "JSON requerido"}), 400
            
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({"success": False, "error": "Email y contraseña son requeridos"}), 400
        
        # Usar Supabase Auth para verificar credenciales
        auth_response = db.client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if auth_response.user:
            auth_user_id = auth_response.user.id
            
            # Buscar el usuario en nuestra tabla usuarios
            user_response = db.client.table('usuarios')\
                .select('id, username')\
                .eq('auth_user_id', auth_user_id)\
                .single()\
                .execute()
            
            if user_response.data:
                return jsonify({
                    "success": True,
                    "user": {
                        "id": user_response.data['id'],
                        "username": user_response.data['username'],
                        "email": email
                    }
                })
            else:
                return jsonify({"success": False, "error": "Usuario no registrado en la aplicación"}), 404
        else:
            return jsonify({"success": False, "error": "Credenciales inválidas"}), 401
            
    except Exception as e:
        logger.error(f"Error en login API: {str(e)}")
        return jsonify({"success": False, "error": "Error al iniciar sesión"}), 500

@api_bp.route('/auth/register', methods=['POST'])
def api_register():
    """
    Endpoint API para registro que devuelve JSON.
    
    POST /api/auth/register
    Body JSON: {"username": "user", "email": "user@example.com", "password": "password"}
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "JSON requerido"}), 400
            
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        if not username or not email or not password:
            return jsonify({"success": False, "error": "Todos los campos son requeridos"}), 400
        
        # Crear usuario en Supabase Auth
        auth_response = db.client.auth.sign_up({
            "email": email,
            "password": password
        })
        
        if auth_response.user:
            auth_user_id = auth_response.user.id
            
            # Crear usuario en nuestra tabla usuarios
            user_response = db.client.table('usuarios')\
                .insert({
                    'username': username,
                    'auth_user_id': auth_user_id
                })\
                .execute()
            
            if user_response.data:
                user_id = user_response.data[0]['id']
                
                # Crear información de contacto
                db.client.table('info_contacto')\
                    .insert({
                        'usuario_id': user_id,
                        'correo_personal': email
                    })\
                    .execute()
                
                return jsonify({
                    "success": True,
                    "user": {
                        "id": user_id,
                        "username": username,
                        "email": email
                    }
                })
            else:
                return jsonify({"success": False, "error": "Error al crear usuario en la aplicación"}), 500
        else:
            return jsonify({"success": False, "error": "Error al crear usuario"}), 500
            
    except Exception as e:
        logger.error(f"Error en registro API: {str(e)}")
        return jsonify({"success": False, "error": "Error al registrar usuario"}), 500

@api_bp.route('/auth/session', methods=['GET'])
def api_session():
    """
    Verifica el estado de la sesión actual.
    
    GET /api/auth/session
    """
    try:
        if 'user_id' in session:
            user_response = db.client.table('usuarios')\
                .select('id, username')\
                .eq('id', session['user_id'])\
                .single()\
                .execute()
            
            if user_response.data:
                return jsonify({
                    "success": True,
                    "logged_in": True,
                    "user": user_response.data
                })
        
        return jsonify({"success": True, "logged_in": False})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route('/user/current', methods=['GET'])
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
        
        # Verificar que el usuario existe
        user_response = db.client.table('usuarios')\
            .select('id, username, email')\
            .eq('id', current_user_id)\
            .single()\
            .execute()
            
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

@api_bp.route('/auth/logout', methods=['POST'])
def api_logout():
    """
    Cierra sesión del usuario actual.
    
    POST /api/auth/logout
    """
    try:
        session.clear()
        return jsonify({"success": True, "message": "Sesión cerrada correctamente"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route('/usuario/<uuid_segment>/qr', methods=['GET'])
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
        
        profile_url = url_for('web.profile', user_id=user_id, _external=True)
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
# Rutas Web
# ====================

@web_bp.route('/')
def home():
    """
    Página principal con diseño moderno y llamadas a la acción.
    
    GET /
    """
    return render_template('pages/home.html')

@web_bp.route('/search')
def search():
    """
    Página de búsqueda con el nuevo template.
    
    GET /search
    """
    return render_template('pages/search.html')

@web_bp.route('/auth-test')
def auth_test():
    """
    Página de prueba para las rutas de autenticación API.
    
    GET /auth-test
    """
    return render_template('pages/auth_test.html')

@web_bp.route('/gestionar-lote')
@AuthManager.login_required
def gestionar_lote():
    """
    Página para gestionar lotes de miel con formulario interactivo.
    
    GET /gestionar-lote
    """
    return render_template('pages/gestionar_lote.html')

@web_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Sistema de acceso para usuarios registrados.
    
    GET /login - Muestra el formulario de login
    POST /login - Procesa el login con email y contraseña
    """
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            return render_template('pages/login.html', error="Email y contraseña son requeridos")
        
        try:
            # Usar AuthManager para manejo consistente de login
            result = AuthManager.login_user(email, password)
            
            if result['success']:
                return redirect(result.get('redirect_url', '/'))
            else:
                return render_template('pages/login.html', error=result['error'])
                
        except Exception as e:
            logger.error(f"Error en login: {str(e)}")
            return render_template('pages/login.html', error="Error al iniciar sesión")
    
    return render_template('pages/login.html')

@web_bp.route('/api/login', methods=['POST'])
def api_login():
    """
    API endpoint para login que devuelve JSON para el frontend JavaScript.
    
    POST /api/login - Procesa login y devuelve JSON
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "JSON requerido"}), 400
        
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({"success": False, "error": "Email y contraseña son requeridos"}), 400
        
        # Usar AuthManager centralizado para evitar duplicación
        result = AuthManager.login_user(email, password)
        
        if result['success']:
            return jsonify({
                "success": True,
                "message": result['message'],
                "redirect_url": result.get('redirect_url', '/')
            })
        else:
            return jsonify({
                "success": False,
                "error": result['error']
            }), result.get('status_code', 400)
            
    except Exception as e:
        logger.error(f"Error en login API: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Error al procesar el login"
        }), 500

@web_bp.route('/logout')
def logout():
    """
    Cierra la sesión del usuario actual
    """
    result = AuthManager.logout_user()
    if result['success']:
        return redirect(result['redirect_url'])
    else:
        return redirect('/login')

@web_bp.route('/debug/oauth')
def debug_oauth():
    """Endpoint de debug para verificar configuración OAuth."""
    from flask import request
    
    debug_info = {
        "request_url_root": request.url_root,
        "callback_url": f"{request.url_root}auth/callback",
        "current_route": request.url,
        "headers": dict(request.headers)
    }
    
    return jsonify(debug_info)

@web_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Página de registro con opciones de Google OAuth y registro manual.
    
    GET /register - Muestra el formulario de registro
    POST /register - Procesa el registro de nuevo usuario
    """
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not username or not email or not password:
            return render_template('pages/register.html', error="Todos los campos son requeridos")
        
        try:
            # Crear usuario en Supabase Auth
            auth_response = db.client.auth.sign_up({
                "email": email,
                "password": password
            })
            
            if auth_response.user:
                auth_user_id = auth_response.user.id
                
                # Crear usuario en nuestra tabla usuarios
                user_response = db.client.table('usuarios')\
                    .insert({
                        'username': username,
                        'auth_user_id': auth_user_id
                    })\
                    .execute()
                
                if user_response.data:
                    user_id = user_response.data[0]['id']
                    
                    # Crear información de contacto
                    db.client.table('info_contacto')\
                        .insert({
                            'usuario_id': user_id,
                            'correo_personal': email
                        })\
                        .execute()
                    
                    session['user_id'] = user_id
                    session['username'] = username
                    return redirect(url_for('web.search'))
                else:
                    # Si falla la creación en nuestra tabla, eliminar el usuario de auth
                    db.client.auth.admin.delete_user(auth_user_id)
                    return render_template('pages/register.html', error="Error al crear usuario en la aplicación")
            else:
                return render_template('pages/register.html', error="Error al crear usuario")
                
        except Exception as e:
            logger.error(f"Error en registro: {str(e)}")
            return render_template('pages/register.html', error="Error al registrar usuario")
    
    return render_template('pages/register.html')

@web_bp.route('/profile/<user_id>')
def profile(user_id):
    """
    Página de perfil de usuario con información completa y QR.
    
    GET /profile/<user_id>
    - user_id: Puede ser el UUID completo, segmento de 8 caracteres, o username
    """
    try:
        # Usar función centralizada para buscar usuario
        user_info = searcher.find_user_by_identifier(user_id)
        
        if not user_info:
            return render_template('pages/profile.html', error="Usuario no encontrado", user=None)
            
        user_uuid = user_info['auth_user_id']
        
        # Obtener información completa del usuario usando función centralizada
        profile_data = searcher.get_user_profile_data(user_uuid)
        
        if not profile_data:
            return render_template('pages/profile.html', error="Usuario no encontrado", user=None)
            
        # Si el ID proporcionado no es el UUID completo, redirigir
        if user_id != user_uuid:
            logger.info(f"Redirigiendo de {user_id} a {user_uuid}")
            return redirect(url_for('web.profile', user_id=user_uuid))
            
        # Preparar datos para la plantilla
        user = profile_data['user']
        contact_info = profile_data['contact_info'] or {}
        locations = profile_data['locations']
        producciones = profile_data['production']
        origenes_botanicos = profile_data['botanical_origins']
        solicitudes = profile_data['requests']
        
        # Crear objeto user para la plantilla
        user_obj = {
            'id': user_uuid,
            'username': user.get('username', 'Usuario'),
            'nombre': user.get('nombre', ''),
            'apellido': user.get('apellido', ''),
            'email': contact_info.get('correo_principal', ''),
            'telefono': contact_info.get('telefono_principal', ''),
            'direccion': contact_info.get('direccion', ''),
            'comuna': contact_info.get('comuna', ''),
            'region': contact_info.get('region', ''),
            'nombre_empresa': contact_info.get('nombre_empresa', ''),
            'descripcion': user.get('descripcion', ''),
            'role': user.get('role', 'Apicultor'),
            'experiencia': user.get('experiencia', ''),
            'produccion_total': sum(p.get('cantidad_kg', 0) for p in producciones),
            'locations': locations,
            'producciones': producciones,
            'qr_url': url_for('api.get_user_qr', uuid_segment=user_uuid[:8], _external=True)
        }
        
        return render_template('pages/profile.html', 
                             user=user_obj,
                             contact_info=contact_info,
                             locations=locations,
                             production=producciones,
                             botanical_origins=origenes_botanicos,
                             requests=solicitudes,
                             qr_url=url_for('api.get_user_qr', uuid_segment=user_uuid[:8], _external=True))
        
    except Exception as e:
        logger.error(f"Error al cargar perfil: {str(e)}")
        return render_template('pages/profile.html', 
                             error="Error al cargar perfil",
                             user=None,
                             contact_info={},
                             locations=[],
                             production=[],
                             botanical_origins=[],
                             requests=[],
                             qr_url=None), 500

# Mantener ruta antigua para compatibilidad
@web_bp.route('/buscar', methods=['GET', 'POST'])
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
                    return redirect(url_for('web.profile', user_id=user_uuid))
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
    
    return redirect(url_for('web.search'))

@web_bp.route('/sugerir', methods=['GET'])
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

# ====================
# Rutas de autenticación OAuth
# ====================

@web_bp.route('/api/auth/google', methods=['GET'])
def api_google_auth():
    """
    API endpoint para iniciar el flujo de autenticación con Google.
    """
    try:
        result = AuthManager.api_google_auth()
        if result.get('success'):
            return redirect(result.get('url'))
        else:
            return redirect('/register')
    except Exception as e:
        logger.error(f"Error en Google auth redirect: {str(e)}")
        return redirect('/register')

@web_bp.route('/auth/callback')
def auth_callback():
    """
    Callback de Google OAuth - maneja tanto código como tokens en fragmentos
    """
    code = request.args.get('code')
    
    # Si hay un código, procesarlo directamente
    if code:
        result = AuthManager.handle_google_callback(code)
        if result['success']:
            return redirect(result['redirect_url'])
        else:
            return redirect(result['redirect_url'])
    
    # Si no hay código, redirigir a la página que maneja tokens en fragmentos
    return render_template('auth/oauth-callback.html')

@web_bp.route('/auth/callback-js', methods=['POST'])
def auth_callback_js():
    """
    Endpoint para manejar tokens OAuth desde JavaScript
    """
    try:
        data = request.get_json()
        access_token = data.get('access_token')
        refresh_token = data.get('refresh_token')
        
        if not access_token:
            return jsonify({
                "success": False,
                "redirect_url": "/register"
            })
        
        # Establecer la sesión con el token recibido
        try:
            # Usar set_session para establecer el token en Supabase
            db.client.auth.set_session(access_token, refresh_token)
            
            # Obtener el usuario actual
            user_response = db.client.auth.get_user()
            
            if user_response and user_response.user:
                user = user_response.user
                logger.info(f"Usuario autenticado vía JS: {user.email}")
                
                # Usar la clase GoogleOAuth para manejar el usuario
                oauth_handler = AuthManager.get_google_oauth()
                user_db_id = oauth_handler._create_or_update_user(user)
                
                # Crear sesión usando el método de OAuth
                oauth_handler._create_session(user, user_db_id, None)
                
                # Almacenar tokens
                session['access_token'] = access_token
                if refresh_token:
                    session['refresh_token'] = refresh_token
                
                return jsonify({
                    "success": True,
                    "redirect_url": f"/profile/{user_db_id}"
                })
            else:
                return jsonify({
                    "success": False,
                    "redirect_url": "/register"
                })
                
        except Exception as e:
            logger.error(f"Error al establecer sesión: {e}")
            return jsonify({
                "success": False,
                "redirect_url": "/register"
            })
            
    except Exception as e:
        logger.error(f"Error en callback JS: {e}")
        return jsonify({
            "success": False,
            "redirect_url": "/register"
        }), 500

@web_bp.route('/api/register', methods=['POST'])
def api_register():
    """
    API endpoint para registro manual de usuarios.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "JSON requerido"}), 400
            
        result = AuthManager.api_register(data)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), result.get('status_code', 400)
            
    except Exception as e:
        logger.error(f"Error en registro API: {str(e)}")
        return jsonify({"success": False, "error": "Error al procesar el registro"}), 500

@web_bp.route('/edit-profile')
@AuthManager.login_required
def edit_profile():
    """
    Página de edición de perfil para usuarios autenticados.
    Solo accesible si el usuario está logueado.
    """
    # Obtener el ID del usuario actual desde la sesión
    current_user_id = session.get('user_id')
    return render_template('pages/edit_profile.html', user_id=current_user_id)
