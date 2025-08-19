"""
Módulo de rutas de autenticación.

Este módulo contiene todas las rutas relacionadas con autenticación:
- Login/logout manual y OAuth
- Registro de usuarios
- Gestión de sesiones
- Callbacks de OAuth
- Endpoints API de autenticación
"""

import logging
from flask import Blueprint, render_template, request, jsonify, url_for, redirect, session
from auth_manager import AuthManager

logger = logging.getLogger(__name__)

# Crear blueprint para rutas de autenticación
auth_bp = Blueprint('auth', __name__)

# ====================
# Rutas Web de Autenticación
# ====================

@auth_bp.route('/login', methods=['GET', 'POST'])
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

@auth_bp.route('/logout')
def logout():
    """
    Cierra la sesión del usuario actual
    """
    result = AuthManager.logout_user()
    if result['success']:
        return redirect(result['redirect_url'])
    else:
        return redirect('/login')

@auth_bp.route('/register', methods=['GET', 'POST'])
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
            # Usar AuthManager para registro consistente
            result = AuthManager.register_user(email, password, username)
            
            if result['success']:
                return redirect(result.get('redirect_url', '/login'))
            else:
                return render_template('pages/register.html', error=result['error'])
                
        except Exception as e:
            logger.error(f"Error en registro: {str(e)}")
            return render_template('pages/register.html', error="Error al registrar usuario")
    
    return render_template('pages/register.html')

@auth_bp.route('/edit-profile')
@AuthManager.login_required
def edit_profile():
    """
    Página de edición de perfil para usuarios autenticados.
    Solo accesible si el usuario está logueado.
    """
    # Obtener el ID del usuario actual desde la sesión
    current_user_id = session.get('user_id')
    return render_template('pages/edit_profile.html', user_id=current_user_id)

# ====================
# Rutas OAuth de Google
# ====================

@auth_bp.route('/api/auth/google', methods=['GET'])
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

@auth_bp.route('/auth/callback')
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

@auth_bp.route('/auth/callback-js', methods=['POST'])
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
            from supabase_client import db
            
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

# ====================
# API Endpoints de Autenticación
# ====================

@auth_bp.route('/api/login', methods=['POST'])
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

@auth_bp.route('/api/auth/login', methods=['POST'])
def api_auth_login():
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
        
        # Usar AuthManager para consistencia
        result = AuthManager.login_user(email, password)
        
        if result['success']:
            return jsonify({
                "success": True,
                "message": result['message']
            })
        else:
            return jsonify({"success": False, "error": result['error']}), result.get('status_code', 401)
            
    except Exception as e:
        logger.error(f"Error en login API: {str(e)}")
        return jsonify({"success": False, "error": "Error al iniciar sesión"}), 500

@auth_bp.route('/api/auth/register', methods=['POST'])
def api_auth_register():
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
        
        # Usar AuthManager para registro
        result = AuthManager.register_user(email, password, username)
        
        if result['success']:
            return jsonify({
                "success": True,
                "message": result['message']
            })
        else:
            return jsonify({"success": False, "error": result['error']}), result.get('status_code', 500)
            
    except Exception as e:
        logger.error(f"Error en registro API: {str(e)}")
        return jsonify({"success": False, "error": "Error al registrar usuario"}), 500

@auth_bp.route('/api/register', methods=['POST'])
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

@auth_bp.route('/api/auth/logout', methods=['POST'])
def api_auth_logout():
    """
    Cierra sesión del usuario actual.
    
    POST /api/auth/logout
    """
    try:
        session.clear()
        return jsonify({"success": True, "message": "Sesión cerrada correctamente"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@auth_bp.route('/api/auth/session', methods=['GET'])
def api_auth_session():
    """
    Verifica el estado de la sesión actual.
    
    GET /api/auth/session
    """
    try:
        if 'user_id' in session:
            from supabase_client import db
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

# ====================
# Rutas de Debug OAuth
# ====================

@auth_bp.route('/debug/oauth')
def debug_oauth():
    """Endpoint de debug para verificar configuración OAuth."""
    debug_info = {
        "request_url_root": request.url_root,
        "callback_url": f"{request.url_root}auth/callback",
        "current_route": request.url,
        "headers": dict(request.headers)
    }
    
    return jsonify(debug_info)
