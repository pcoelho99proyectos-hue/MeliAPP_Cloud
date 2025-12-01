"""
Módulo de rutas API REST de autenticación.

Este módulo contiene SOLO endpoints API REST que devuelven JSON:
- Registro de usuarios
- Login/logout
- Gestión de sesiones
- Confirmación de email
- Cambio de contraseña
- OAuth (solo para API)

IMPORTANTE: Este módulo NO contiene rutas web que devuelvan HTML.
Todas las respuestas son JSON para consumo desde aplicaciones móviles o clientes HTTP.
"""

import logging
import os
import traceback
from flask import Blueprint, request, jsonify, session
from supabase_client import db
from auth_manager import AuthManager

logger = logging.getLogger(__name__)

# Crear blueprint para API REST de autenticación
auth_bp = Blueprint('auth', __name__)

# ====================
# API REST - Autenticación
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
    
    Returns:
        JSON: {"success": bool, "message": str}
    """
    try:
        session.clear()
        return jsonify({"success": True, "message": "Sesión cerrada correctamente"})
    except Exception as e:
        logger.error(f"Error en logout: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@auth_bp.route('/api/auth/session', methods=['GET'])
def api_auth_session():
    """
    Verifica el estado de la sesión actual.
    
    GET /api/auth/session
    
    Returns:
        JSON: {
            "success": bool,
            "logged_in": bool,
            "user": dict (opcional)
        }
    """
    try:
        if 'user_id' in session:
            user_response = db.client.table('usuarios')\
                .select('auth_user_id, username')\
                .eq('auth_user_id', session['user_id'])\
                .maybe_single()\
                .execute()
            
            if user_response.data:
                return jsonify({
                    "success": True,
                    "logged_in": True,
                    "user": {
                        "id": user_response.data['auth_user_id'],
                        "username": user_response.data['username']
                    }
                })
        
        return jsonify({"success": True, "logged_in": False})
        
    except Exception as e:
        logger.error(f"Error verificando sesión: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

# ====================
# API REST - Confirmación de Email
# ====================

@auth_bp.route('/api/auth/confirm', methods=['GET', 'POST'])
def api_confirm_email():
    """
    API REST endpoint para confirmar email de usuario.
    
    GET /api/auth/confirm?token_hash=XXX&type=email
    POST /api/auth/confirm con JSON: {"token_hash": "XXX", "type": "email"}
    
    Returns:
        JSON: {
            "success": bool,
            "message": str,
            "user_data": dict (si success=True)
        }
    """
    try:
        # Soportar tanto GET como POST
        if request.method == 'GET':
            token_hash = request.args.get('token_hash')
            type_param = request.args.get('type', 'email')
        else:
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'message': 'JSON requerido para POST request'
                }), 400
            token_hash = data.get('token_hash')
            type_param = data.get('type', 'email')
        
        if not token_hash:
            logger.error("Token de confirmación faltante en API request")
            return jsonify({
                'success': False,
                'message': 'Token de confirmación es requerido'
            }), 400
        
        # Verificar confirmación e inicializar tablas
        success, message, user_data = AuthManager.verify_email_confirmation(token_hash, type_param)
        
        if success:
            logger.info(f"✅ Confirmación API exitosa para usuario: {user_data.get('email', 'desconocido')}")
            return jsonify({
                'success': True,
                'message': message,
                'user_data': {
                    'user_id': user_data.get('user_id'),
                    'email': user_data.get('email'),
                    'user_metadata': user_data.get('user_metadata', {})
                }
            }), 200
        else:
            logger.error(f"❌ Error en confirmación API: {message}")
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        logger.error(f"Excepción procesando confirmación API: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error interno procesando confirmación de email'
        }), 500

@auth_bp.route('/api/auth/resend-confirmation', methods=['POST'])
def api_resend_confirmation():
    """
    API REST endpoint para reenviar email de confirmación.
    
    POST /api/auth/resend-confirmation
    Body JSON: {"email": "user@example.com"}
    
    Returns:
        JSON: {"success": bool, "message": str}
    """
    try:
        data = request.get_json()
        email = data.get('email') if data else None
        
        if not email:
            return jsonify({
                'success': False,
                'message': 'Email es requerido'
            }), 400
        
        success, message = AuthManager.resend_confirmation_email(email)
        
        return jsonify({
            'success': success,
            'message': message
        }), 200 if success else 400
        
    except Exception as e:
        logger.error(f"Error reenviando confirmación: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error interno del servidor'
        }), 500

# ====================
# API REST - Gestión de Contraseñas
# ====================

@auth_bp.route('/api/auth/forgot-password', methods=['POST'])
def api_forgot_password():
    """
    API REST endpoint público para solicitar reseteo de contraseña.
    No requiere autenticación.
    
    POST /api/auth/forgot-password
    Body JSON: {"email": "user@example.com"}
    
    Returns:
        JSON: {"success": bool, "message": str}
    """
    try:
        data = request.get_json()
        if not data or 'email' not in data:
            return jsonify({
                'success': False,
                'error': 'Email es requerido'
            }), 400
        
        email = data.get('email').strip()
        
        if not email:
            return jsonify({
                'success': False,
                'error': 'Email no puede estar vacío'
            }), 400
        
        # Llamar a AuthManager para enviar email de reseteo
        result = AuthManager.request_password_reset(email)
        
        # Siempre retornar success=True por seguridad (no revelar si email existe)
        return jsonify({
            'success': True,
            'message': 'Si el correo está registrado, recibirás un enlace para recuperar tu contraseña.'
        }), 200
        
    except Exception as e:
        logger.error(f"Error en forgot-password: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500

@auth_bp.route('/reset-password', methods=['GET'])
def reset_password_page():
    """
    Página web para restablecer contraseña.
    El usuario llega aquí desde el email con el token.
    
    GET /reset-password?token=xxx o?access_token=xxx
    """
    from flask import render_template
    return render_template('pages/reset_password.html')

@auth_bp.route('/api/auth/reset-password', methods=['POST'])
def api_reset_password():
    """
    API REST para completar el reseteo de contraseña con token.
    
    POST /api/auth/reset-password
    Body JSON: {
        "token": "access_token_from_email",
        "password": "new_password"
    }
    
    Returns:
        JSON: {"success": bool, "message": str}
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No se recibieron datos'
            }), 400
        
        token = data.get('token')
        new_password = data.get('password')
        
        if not token or not new_password:
            return jsonify({
                'success': False,
                'error': 'Token y contraseña son requeridos'
            }), 400
        
        if len(new_password) < 6:
            return jsonify({
                'success': False,
                'error': 'La contraseña debe tener al menos 6 caracteres'
            }), 400
        
        # Actualizar contraseña usando el token de recuperación
        try:
            import requests
            
            # Obtener URL de Supabase desde variables de entorno
            supabase_url = os.getenv('SUPABASE_URL')
            supabase_key = os.getenv('SUPABASE_KEY')
            
            if not supabase_url or not supabase_key:
                logger.error("❌ Variables SUPABASE_URL o SUPABASE_KEY no configuradas")
                return jsonify({
                    'success': False,
                    'error': 'Error de configuración del servidor'
                }), 500
            
            # Llamar a la API REST de Supabase directamente
            url = f"{supabase_url}/auth/v1/user"
            headers = {
                'Authorization': f'Bearer {token}',
                'apikey': supabase_key,
                'Content-Type': 'application/json'
            }
            payload = {
                'password': new_password
            }
            
            response = requests.put(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                logger.info(f"✅ Contraseña actualizada exitosamente")
                return jsonify({
                    'success': True,
                    'message': 'Contraseña actualizada correctamente'
                }), 200
            else:
                error_data = response.json() if response.text else {}
                logger.error(f"❌ Error de Supabase al actualizar contraseña: {response.status_code} - {error_data}")
                return jsonify({
                    'success': False,
                    'error': 'Token inválido o expirado. Solicita un nuevo enlace de recuperación.'
                }), 400
            
        except Exception as supabase_error:
            logger.error(f"❌ Error al actualizar contraseña: {str(supabase_error)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return jsonify({
                'success': False,
                'error': 'Error al procesar la solicitud. Por favor intenta nuevamente.'
            }), 400
        
    except Exception as e:
        logger.error(f"❌ Error en reset-password: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500

@auth_bp.route('/api/auth/change-password', methods=['POST'])
@AuthManager.login_required
def handle_change_password():
    """
    Cambia la contraseña del usuario autenticado.
    
    POST /api/auth/change-password
    Body JSON: {
        "current_password": "old_password",
        "new_password": "new_password"
    }
    
    Returns:
        JSON: {"success": bool, "message": str}
    """
    data = request.get_json()
    if not data or 'current_password' not in data or 'new_password' not in data:
        return jsonify({
            "success": False,
            "error": "Faltan parámetros: contraseña actual y nueva son requeridas."
        }), 400

    current_password = data.get('current_password')
    new_password = data.get('new_password')

    result = AuthManager.change_user_password(current_password, new_password)

    status_code = result.get('status_code', 200 if result.get('success') else 500)
    return jsonify(result), status_code

# ====================
# API REST - OAuth Google
# ====================

@auth_bp.route('/api/auth/google', methods=['POST'])
def api_google_auth():
    """
    API REST endpoint para iniciar flujo OAuth con Google.
    
    POST /api/auth/google
    
    Returns:
        JSON: {
            "success": bool,
            "url": str (URL para redirigir al usuario)
        }
    """
    try:
        result = AuthManager.api_google_auth()
        if result.get('success'):
            return jsonify({
                "success": True,
                "url": result.get('url')
            })
        else:
            return jsonify({
                "success": False,
                "error": result.get('error', 'Error generando URL OAuth')
            }), 500
    except Exception as e:
        logger.error(f"Error en Google auth: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Error al iniciar autenticación con Google"
        }), 500

@auth_bp.route('/api/auth/google/callback', methods=['POST'])
def api_google_callback():
    """
    API REST endpoint para procesar callback de OAuth Google con código.
    
    POST /api/auth/google/callback
    Body JSON: {"code": "authorization_code"}
    
    Returns:
        JSON: {
            "success": bool,
            "message": str,
            "user": dict (opcional)
        }
    """
    try:
        data = request.get_json()
        code = data.get('code') if data else None
        
        if not code:
            return jsonify({
                "success": False,
                "error": "Código de autorización requerido"
            }), 400
        
        result = AuthManager.handle_google_callback(code)
        
        if result['success']:
            return jsonify({
                "success": True,
                "message": "Autenticación exitosa",
                "redirect_url": result.get('redirect_url', '/edit-profile')
            })
        else:
            return jsonify({
                "success": False,
                "error": result.get('error', 'Error en autenticación')
            }), 401
            
    except Exception as e:
        logger.error(f"Error en callback OAuth: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Error procesando callback de Google"
        }), 500

@auth_bp.route('/api/auth/oauth/tokens', methods=['POST'])
def api_oauth_tokens():
    """
    API REST endpoint para procesar tokens OAuth del fragmento (#).
    
    POST /api/auth/oauth/tokens
    Body JSON: {
        "access_token": "...",
        "refresh_token": "..."
    }
    
    Este endpoint maneja el flujo implícito de OAuth donde Google devuelve
    los tokens directamente en el fragmento (#) de la URL.
    
    Returns:
        JSON: {
            "success": bool,
            "message": str,
            "redirect_url": str
        }
    """
    try:
        logger.info("=== INICIO PROCESAMIENTO TOKENS OAUTH ===")
        
        data = request.get_json()
        access_token = data.get('access_token') if data else None
        refresh_token = data.get('refresh_token') if data else None
        
        if not access_token:
            logger.error("❌ Access token faltante")
            return jsonify({
                "success": False,
                "error": "Access token requerido"
            }), 400
        
        logger.info(f"✅ Tokens recibidos - Access: {access_token[:20]}...")
        
        # Establecer sesión en Supabase con los tokens
        from supabase_client import db
        db.client.auth.set_session(access_token, refresh_token)
        
        # Obtener usuario con el token
        user_response = db.client.auth.get_user()
        
        if not user_response or not user_response.user:
            logger.error("❌ No se pudo obtener usuario con el token")
            return jsonify({
                "success": False,
                "error": "Token inválido"
            }), 401
        
        user = user_response.user
        logger.info(f"👤 Usuario OAuth: {user.email}")
        logger.info(f"📧 Email verificado: {user.email_confirmed_at is not None}")
        
        # VERIFICACIÓN: Email debe estar verificado por el proveedor
        if not user.email_confirmed_at:
            logger.error(f"❌ Email no verificado: {user.email}")
            return jsonify({
                "success": False,
                "error": "Email no ha sido verificado por el proveedor"
            }), 403
        
        logger.info(f"✅ Email verificado por proveedor OAuth")
        
        # Verificar si usuario existe en nuestras tablas
        auth_user_id = str(user.id)
        user_check = db.client.table('usuarios')\
            .select('auth_user_id')\
            .eq('auth_user_id', auth_user_id)\
            .maybe_single()\
            .execute()
        
        redirect_url = '/'
        
        if user_check and user_check.data:
            # Usuario existente
            logger.info(f"👤 Usuario existente: {user.email}")
        else:
            # Usuario nuevo - inicializar tablas
            logger.info(f"🆕 Usuario nuevo de OAuth, inicializando...")
            
            user_metadata = user.user_metadata or {}
            initialization_success = AuthManager.initialize_user_tables_on_confirmation(
                auth_user_id,
                user.email,
                user_metadata
            )
            
            if not initialization_success:
                logger.error(f"❌ Error inicializando tablas para: {user.email}")
                return jsonify({
                    "success": False,
                    "error": "Error al crear el perfil de usuario"
                }), 500
            
            logger.info(f"✅ Tablas inicializadas para: {user.email}")
            redirect_url = '/edit-profile'
        
        # Crear sesión Flask
        session['user_id'] = auth_user_id
        session['user_email'] = user.email
        session['user_name'] = user.user_metadata.get('full_name', user.email.split('@')[0])
        session['access_token'] = access_token
        if refresh_token:
            session['refresh_token'] = refresh_token
        
        logger.info(f"✅ Sesión creada exitosamente para: {user.email}")
        
        return jsonify({
            "success": True,
            "message": "Autenticación exitosa",
            "redirect_url": redirect_url
        })
        
    except Exception as e:
        logger.error(f"❌ Error procesando tokens OAuth: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Error en el proceso de autenticación"
        }), 500
