"""
Módulo de autenticación y gestión de sesiones de usuario.

Este módulo maneja todo lo relacionado con:
- Registro de usuarios
- Login/logout
- Autenticación con Google OAuth
- Gestión de sesiones
- Decoradores de autenticación
"""

import logging
from functools import wraps
from flask import session, request, redirect, url_for, flash, g, jsonify, current_app
import uuid
from datetime import datetime
from supabase_client import db

# logger = logging.getLogger(__name__)

class AuthManager:
    """Gestor centralizado de autenticación y sesiones de usuario."""
    
    @staticmethod
    def login_required(f):
        """
        Decorador que requiere que el usuario esté autenticado.
        Si no está autenticado, redirige a la página de login.
        
        Args:
            f: Función a decorar
            
        Returns:
            Función decorada que verifica autenticación
        """
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('web.login'))
            return f(*args, **kwargs)
        return decorated_function
    
    @staticmethod
    def load_current_user():
        """
        Carga la información del usuario actual en g.user para todas las peticiones.
        Mapea el UUID de autenticación al UUID de la tabla usuarios usando la función del searcher.
        """
        g.user = None
        if 'user_id' in session:
            auth_user_id = session.get('user_id')
            
            # Obtener el UUID de la tabla usuarios - método único y eficiente
            user_uuid = auth_user_id  # Por defecto, usar el auth_user_id como UUID del perfil
            
            # Solo buscar si realmente necesitamos mapear (para compatibilidad futura)
            try:
                response = db.client.table('usuarios').select('id').eq('auth_user_id', auth_user_id).execute()
                if response.data and len(response.data) > 0:
                    user_uuid = response.data[0]['id']
            except Exception as e:
                # Silencioso para evitar spam en logs
                pass
            
            g.user = {
                'id': auth_user_id,  # UUID de autenticación
                'user_uuid': user_uuid,  # UUID de la tabla usuarios (obtenido con searcher)
                'name': session.get('user_name'),
                'email': session.get('user_email'),
                'empresa': session.get('user_empresa', '')
            }
    
    @staticmethod
    def login_user(email: str, password: str):
        """
        Autentica un usuario con email y contraseña.
        
        Args:
            email: Email del usuario
            password: Contraseña del usuario
            
        Returns:
            dict: Resultado de la autenticación
        """
        try:
            if not email or not password:
                return {
                    "success": False,
                    "error": "Email y contraseña son requeridos",
                    "status_code": 400
                }
            
            # Autenticar con Supabase Auth
            auth_response = db.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if not auth_response.user:
                return {
                    "success": False,
                    "error": "Credenciales inválidas",
                    "status_code": 401
                }
            
            user = auth_response.user
            
            # Obtener información adicional del usuario desde info_contacto
            contact_response = db.client.table('info_contacto')\
                .select('id, nombre_completo, nombre_empresa')\
                .eq('usuario_id', user.id)\
                .execute()
            
            contact_info = contact_response.data[0] if contact_response.data else {}
            
            # Buscar el ID de la tabla usuarios correspondiente al auth_user_id
            user_mapping = db.client.table('usuarios')\
                .select('id')\
                .eq('auth_user_id', user.id)\
                .single()\
                .execute()
            
            if user_mapping.data:
                user_uuid = user_mapping.data['id']
            else:
                # Si no existe en usuarios, usar el auth_user_id como fallback
                user_uuid = str(user.id)
            
            # Crear sesión de usuario
            session['user_id'] = user_uuid  # ID de la tabla usuarios
            session['auth_user_id'] = str(user.id)  # ID de autenticación
            session['user_email'] = user.email
            session['user_name'] = contact_info.get('nombre_completo') or user.user_metadata.get('full_name', user.email)
            session['user_empresa'] = contact_info.get('nombre_empresa', '')
            
            # Almacenar tokens JWT para RLS
            try:
                # Extraer tokens correctamente de la respuesta de Supabase
                session_data = auth_response.session
                if session_data:
                    session['access_token'] = session_data.access_token
                    session['refresh_token'] = session_data.refresh_token
                    current_app.logger.info(f"JWT tokens stored in session for user: {user.email}")
                else:
                    current_app.logger.error("No session data in auth response")
            except Exception as e:
                current_app.logger.error(f"Error almacenando tokens JWT: {str(e)}")
            
            return {
                "success": True,
                "message": "Login exitoso",
                "redirect_url": "/",
                "status_code": 200
            }
            
        except Exception as e:
            error_message = str(e)
            current_app.logger.error(f"Error en login: {error_message}")
            
            # Manejar específicamente errores de autenticación de Supabase
            if "Invalid login credentials" in error_message:
                return {
                    "success": False,
                    "error": "Credenciales inválidas",
                    "status_code": 401
                }
            elif "NetworkError" in error_message or "ConnectionError" in error_message:
                return {
                    "success": False,
                    "error": "Error de conexión con el servidor de autenticación",
                    "status_code": 503
                }
            else:
                # Para cualquier otro error, incluidos errores HTML
                return {
                    "success": False,
                    "error": "Error al procesar la solicitud de login",
                    "status_code": 500
                }
    
    @staticmethod
    def logout_user():
        """Cierra la sesión del usuario actual."""
        session.clear()
        return {
            "success": True,
            "redirect_url": "/login"
        }
    
    @staticmethod
    def register_user(email: str, password: str, full_name: str, company: str = ""):
        """
        Registra un nuevo usuario.
        
        Args:
            email: Email del usuario
            password: Contraseña del usuario
            full_name: Nombre completo del usuario
            company: Nombre de la empresa (opcional)
            
        Returns:
            dict: Resultado del registro
        """
        try:
            if not email or not password or not full_name:
                return {
                    "success": False,
                    "error": "Todos los campos son requeridos",
                    "status_code": 400
                }
            
            if len(password) < 6:
                return {
                    "success": False,
                    "error": "La contraseña debe tener al menos 6 caracteres",
                    "status_code": 400
                }
            
            # Crear usuario con Supabase Auth
            auth_response = db.client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "full_name": full_name,
                        "company": company
                    }
                }
            })
            
            if not auth_response.user:
                return {
                    "success": False,
                    "error": "Error al crear usuario",
                    "status_code": 400
                }
            
            user = auth_response.user
            
            # Crear entrada en info_contacto si no existe
            try:
                db.client.table('info_contacto').insert({
                    "usuario_id": str(user.id),
                    "nombre_completo": full_name,
                    "nombre_empresa": company,
                    "correo_principal": email
                }).execute()
            except Exception as e:
                current_app.logger.warning(f"Error al crear info_contacto: {str(e)}")
            
            return {
                "success": True,
                "message": "Usuario creado exitosamente",
                "redirect_url": "/login",
                "status_code": 200
            }
            
        except Exception as e:
            current_app.logger.error(f"Error en registro: {str(e)}")
            return {
                "success": False,
                "error": "Error al crear cuenta",
                "status_code": 500
            }
    
    @staticmethod
    def _get_base_url():
        """
        Obtiene la URL base dinámica según el entorno.
        
        Returns:
            str: URL base completa
        """
        # Detectar si estamos en producción (Vercel)
        if request.environ.get('HTTP_X_FORWARDED_HOST'):
            protocol = request.environ.get('HTTP_X_FORWARDED_PROTO', 'https')
            host = request.environ.get('HTTP_X_FORWARDED_HOST')
            return f"{protocol}://{host}"
        else:
            # Desarrollo local
            return request.url_root.rstrip('/')
    
    @staticmethod
    def init_google_oauth_flow(is_api=False):
        """
        Método único y unificado para iniciar el flujo de autenticación con Google OAuth.
        
        Args:
            is_api (bool): Si es True, retorna formato JSON. Si es False, retorna formato web.
            
        Returns:
            dict: URL de redirección para Google OAuth
        """
        try:
            current_app.logger.info(f" Iniciando init_google_oauth_flow - is_api: {is_api}")
            
            base_url = AuthManager._get_base_url()
            redirect_uri = f"{base_url}/auth/callback"
            
            current_app.logger.info(f" URL base detectada: {base_url}")
            current_app.logger.info(f" URL de redirección: {redirect_uri}")
            
            auth_response = db.client.auth.sign_in_with_oauth({
                "provider": "google",
                "options": {
                    "redirect_to": redirect_uri,
                    "scopes": "email profile openid",
                    "skip_browser_redirect": False
                }
            })
            
            current_app.logger.info(f" Respuesta de Supabase auth recibida")
            current_app.logger.info(f" auth_response type: {type(auth_response)}")
            
            if hasattr(auth_response, 'url'):
                current_app.logger.info(f" URL generada exitosamente: {auth_response.url}")
                return {
                    "success": True,
                    "url": auth_response.url,
                    "url_web": auth_response.url if not is_api else None
                }
            else:
                current_app.logger.error(" auth_response no tiene atributo 'url'")
                current_app.logger.error(f" auth_response: {auth_response}")
                return {
                    "success": False,
                    "error": "Error al generar URL de Google",
                    "status_code": 500
                }
                
        except Exception as e:
            current_app.logger.error(f" Error en init_google_oauth_flow: {str(e)}")
            current_app.logger.error(f" Tipo de error: {type(e).__name__}")
            import traceback
            current_app.logger.error(f" Traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "error": "Error al conectar con Google",
                "status_code": 500
            }

    @staticmethod
    def init_google_auth():
        """
        Inicia el flujo de autenticación con Google OAuth (versión web).
        
        Returns:
            dict: URL de redirección para Google OAuth
        """
        return AuthManager.init_google_oauth_flow(is_api=False)

    @staticmethod
    def api_google_auth():
        """
        API endpoint para iniciar el flujo de autenticación con Google OAuth.
        
        Returns:
            dict: Respuesta JSON con la URL de redirección
        """
        return AuthManager.init_google_oauth_flow(is_api=True)
    
    @staticmethod
    def handle_google_callback(code: str):
        """
        Maneja el callback de Google OAuth.
        
        Args:
            code: Código de autorización de Google
            
        Returns:
            dict: Resultado del proceso de autenticación
        """
        try:
            current_app.logger.info(f" INICIANDO handle_google_callback")
            current_app.logger.info(f" Código recibido: {code}")
            current_app.logger.info(f" Tipo de código: {type(code)}")
            current_app.logger.info(f" Sesión actual: {dict(session)}")
            
            # Si no hay código, verificar si hay sesión activa
            if not code:
                current_app.logger.warning(" No se recibió código, verificando sesión activa")
                
                # Verificar si ya hay un usuario autenticado
                try:
                    current_user = db.client.auth.get_user()
                    if current_user and current_user.user:
                        current_app.logger.info(f" Usuario ya autenticado encontrado: {current_user.user.email}")
                        return {
                            "success": True,
                            "message": "Usuario ya autenticado",
                            "user": current_user.user
                        }
                except Exception as auth_error:
                    current_app.logger.error(f" Error al verificar sesión activa: {auth_error}")
            
            current_app.logger.info(" Obteniendo usuario desde Supabase Auth...")
            
            # Obtener usuario actual desde Supabase Auth
            user = db.client.auth.get_user()
            
            if not user:
                current_app.logger.error(" No se pudo obtener usuario desde Supabase Auth")
                current_app.logger.error(f" Respuesta de get_user(): {user}")
                return {
                    "success": False,
                    "error": "Usuario no encontrado",
                    "status_code": 404
                }
            
            current_app.logger.info(f" Usuario autenticado exitosamente: {user.user.email}")
            current_app.logger.info(f" ID de usuario: {user.user.id}")
            current_app.logger.info(f" Metadata: {user.user.user_metadata}")
            
            # Guardar datos del usuario en la sesión
            session['user_id'] = user.user.id
            session['user_email'] = user.user.email
            session['user_metadata'] = user.user.user_metadata
            
            current_app.logger.info(" Datos guardados en sesión")
            current_app.logger.info(f" Sesión actualizada: {dict(session)}")
            
            # Verificar si el usuario existe en nuestra base de datos
            current_app.logger.info(f" Buscando usuario existente: {user.user.email}")
            existing_user = db.client.table('usuarios').select('*').eq('email', user.user.email).execute()
            
            current_app.logger.info(f" Resultado búsqueda usuario: {existing_user}")
            
            if existing_user.data:
                current_app.logger.info(f" Usuario existente encontrado: {user.user.email}")
                current_app.logger.info(f" Datos usuario existente: {existing_user.data[0]}")
                return {
                    "success": True,
                    "message": "Usuario autenticado exitosamente",
                    "user": existing_user.data[0]
                }
            else:
                current_app.logger.info(f" Nuevo usuario detectado: {user.user.email}")
                
                # Crear nuevo usuario
                new_user_data = {
                    'email': user.user.email,
                    'nombre': user.user.user_metadata.get('full_name', user.user.email),
                    'fecha_registro': datetime.now().isoformat(),
                    'google_id': user.user.id,
                    'avatar_url': user.user.user_metadata.get('avatar_url', '')
                }
                
                current_app.logger.info(f" Datos para nuevo usuario: {new_user_data}")
                
                result = db.client.table('usuarios').insert(new_user_data).execute()
                
                current_app.logger.info(f" Resultado inserción: {result}")
                
                if result.data:
                    current_app.logger.info(f" Nuevo usuario creado exitosamente: {user.user.email}")
                    current_app.logger.info(f" Datos usuario creado: {result.data[0]}")
                    return {
                        "success": True,
                        "message": "Usuario registrado exitosamente",
                        "user": result.data[0]
                    }
                else:
                    current_app.logger.error(f" Error al crear usuario: {user.user.email}")
                    current_app.logger.error(f" Error detalles: {result}")
                    return {
                        "success": False,
                        "error": "Error al registrar usuario",
                        "status_code": 500
                    }
                
        except Exception as e:
            current_app.logger.error(f" ERROR CRÍTICO en handle_google_callback: {str(e)}")
            current_app.logger.error(f" Tipo de error: {type(e).__name__}")
            import traceback
            current_app.logger.error(f" Traceback completo: {traceback.format_exc()}")
            return {
                "success": False,
                "error": "Error en el proceso de autenticación",
                "status_code": 500
            }

    @staticmethod
    def api_register(data):
        """
        API endpoint para registro manual de usuarios.
        
        Args:
            data: Diccionario con los datos del usuario
            
        Returns:
            dict: Resultado del registro
        """
        try:
            email = data.get('email')
            password = data.get('password')
            full_name = data.get('nombre')
            company = data.get('telefono', '')
            
            return AuthManager.register_user(email, password, full_name, company)
            
        except Exception as e:
            logger.error(f"Error en registro API: {str(e)}")
            return {
                "success": False,
                "error": "Error al procesar el registro",
                "status_code": 500
            }
    
    @staticmethod
    def is_authenticated():
        """Verifica si el usuario está autenticado."""
        return 'user_id' in session
    
    @staticmethod
    def get_current_user():
        """Obtiene la información del usuario actual."""
        return g.user if hasattr(g, 'user') else None
    
    @staticmethod
    def get_user_id():
        """Obtiene el ID del usuario autenticado."""
        return session.get('user_id')
    
    @staticmethod
    def get_user_email():
        """Obtiene el email del usuario autenticado."""
        return session.get('user_email')
    
    @staticmethod
    def get_user_name():
        """Obtiene el nombre del usuario autenticado."""
        return session.get('user_name')


# Instancia global para importar fácilmente
auth_manager = AuthManager()
