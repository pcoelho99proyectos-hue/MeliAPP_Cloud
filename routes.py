"""
Módulo de rutas y endpoints para la aplicación MeliAPP_v2.

Este módulo contiene todas las rutas Flask organizadas por categorías:
- Rutas de API
- Rutas web
- Rutas de autenticación (delegadas a auth_manager)
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
from auth_manager import auth_manager
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
        success, message = db.test_connection()
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
@auth_manager.login_required
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
        response = db.client.table('usuarios').select('id').limit(1).execute()
        
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
            .select('id')\
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
            .select('id')\
            .execute()
            
        if not response.data:
            return jsonify({"error": "No hay usuarios en la base de datos"}), 404
            
        # Filtrar usuarios cuyo ID comience con el segmento
        matching_users = [user for user in response.data if str(user['id']).startswith(uuid_segment)]
            
        if not matching_users:
            return jsonify({"error": "Usuario no encontrado"}), 404
            
        user_id = matching_users[0]['id']
        
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
@auth_manager.login_required
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
    Cierra la sesión del usuario actual.
    
    GET /logout - Cierra sesión y redirige al login
    """
    session.clear()
    return redirect(url_for('web.login'))

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
    - user_id: Puede ser el UUID completo o el segmento de 8 caracteres
    """
    try:
        import uuid
        user_uuid = None
        user_info = None
        
        try:
            uuid.UUID(user_id)
            user_uuid = user_id
            
            user_response = searcher.supabase.table('usuarios').select('*').eq('id', user_uuid).execute()
            if not user_response.data:
                return render_template('pages/profile.html', error="Usuario no encontrado"), 404
            user_info = user_response.data[0]
                
        except ValueError:
            if len(user_id) == 8:
                search_response = searcher.supabase.table('usuarios')\
                    .select('*')\
                    .like('id', f'{user_id}%')\
                    .limit(1)\
                    .execute()
                
                if search_response.data:
                    user_info = search_response.data[0]
                    user_uuid = user_info['id']
                else:
                    return render_template('pages/profile.html', error="Usuario no encontrado"), 404
            else:
                if len(user_id) >= 2:
                    search_response = searcher.supabase.table('usuarios')\
                        .select('*')\
                        .ilike('username', f'%{user_id}%')\
                        .limit(1)\
                        .execute()
                    
                    if search_response.data:
                        user_info = search_response.data[0]
                        user_uuid = user_info['id']
                    else:
                        return render_template('pages/profile.html', error="Usuario no encontrado"), 404
                else:
                    return render_template('pages/profile.html', error="Por favor ingresa al menos 2 caracteres"), 400
        
        contact_response = db.client.table('info_contacto').select('*').eq('usuario_id', user_uuid).execute()
        contact_info = contact_response.data[0] if contact_response.data else {}
        
        locations_response = db.client.table('ubicaciones').select('*').eq('usuario_id', user_uuid).execute()
        locations = locations_response.data if locations_response.data else []
        
        qr_url = url_for('api.get_user_qr', uuid_segment=user_uuid[:8], _external=True)
        
        # Validar que se encontró información de contacto
        if not contact_response.data:
            logger.info(f"No se encontró información de contacto para usuario_id: {user_uuid}")
        
        user_template_data = {
            'id': user_uuid,
            'nombre': user_info.get('username', 'Usuario'),
            'email': contact_info.get('correo_principal', ''),  # ✅ Corregido: correo_principal
            'telefono': contact_info.get('telefono_principal', ''),  # ✅ Corregido: telefono_principal
            'direccion': contact_info.get('direccion', ''),
            'comuna': contact_info.get('comuna', ''),
            'region': contact_info.get('region', ''),
            'nombre_empresa': contact_info.get('nombre_empresa', ''),
            'nombre_completo': contact_info.get('nombre_completo', ''),
            'ubicacion': locations[0].get('nombre') if locations else None,
            'descripcion': user_info.get('descripcion', ''),
            'especialidad': user_info.get('role', 'Apicultor'),
            'especialidades': [user_info.get('role')] if user_info.get('role') else [],
            'especialidades_completas': [user_info.get('role')] if user_info.get('role') else [],
            'contacto_completo': contact_info,
            'ubicaciones': locations
        }
        
        return render_template('pages/profile.html', user=user_template_data, qr_url=qr_url)
                               
    except Exception as e:
        logger.error(f"Error al cargar perfil: {str(e)}", exc_info=True)
        return render_template('pages/profile.html', user=None, error="Error al cargar el perfil"), 500

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
                if len(search_term) >= 2:
                    search_response = searcher.supabase.table('usuarios')\
                        .select('id', 'username', 'role')\
                        .ilike('username', f'%{search_term}%')\
                        .limit(10)\
                        .execute()
                    
                    if not search_response.data:
                        search_response = searcher.supabase.table('usuarios')\
                            .select('id', 'username', 'role')\
                            .eq('id', search_term)\
                            .limit(1)\
                            .execute()
                    
                    if search_response.data:
                        user = search_response.data[0]
                        return redirect(url_for('web.profile', user_id=user['id']))
                    else:
                        return render_template('pages/search.html', error="Usuario no encontrado")
                else:
                    return render_template('pages/search.html', error="Por favor ingresa al menos 2 caracteres")
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
        if not termino:
            return jsonify({'suggestions': []})
            
        response = searcher.supabase.table('usuarios') \
            .select('id, username, tipo_usuario, status') \
            .ilike('username', f'%{termino}%') \
            .limit(10) \
            .execute()
            
        users = response.data if hasattr(response, 'data') else []
        
        suggestions = [{
            'id': user['id'],
            'nombre': user.get('username', ''),
            'especialidad': user.get('role', 'Apicultor')
        } for user in users]
        
        return jsonify({'suggestions': suggestions})
        
    except Exception as e:
        logger.error(f"Error en /sugerir: {str(e)}", exc_info=True)
        return jsonify({"error": "Error al obtener sugerencias"}), 500

# ====================
# Rutas de autenticación OAuth
# ====================

@web_bp.route('/api/auth/google', methods=['POST'])
def api_google_auth():
    """
    API endpoint para iniciar el flujo de autenticación con Google.
    """
    return auth_manager.api_google_auth()

@web_bp.route('/auth/callback')
def auth_callback():
    """
    Callback para manejar el retorno de Google OAuth.
    """
    return auth_manager.auth_callback()

@web_bp.route('/api/register', methods=['POST'])
def api_register():
    """
    API endpoint para registro manual de usuarios.
    """
    return auth_manager.api_register()

@web_bp.route('/edit-profile')
@auth_manager.login_required
def edit_profile():
    """
    Página de edición de perfil para usuarios autenticados.
    Solo accesible si el usuario está logueado.
    """
    return render_template('pages/edit_profile.html')
