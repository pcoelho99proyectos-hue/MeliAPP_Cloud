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
import os
from functools import wraps
from flask import session, request, redirect, url_for, flash, g, jsonify, current_app
import uuid
from datetime import datetime
from supabase_client import db

logger = logging.getLogger(__name__)

class GoogleOAuth:
    """Clase unificada para manejar todo el flujo OAuth de Google"""
    
    def __init__(self):
        self.provider = 'google'
    
    def get_base_url(self):
        """Obtiene la URL base dinámica"""
        from app import get_base_url
        return get_base_url()
    
    def generate_auth_url(self):
        """Genera la URL de autenticación OAuth"""
        try:
            logger.info("Generando URL de autenticación OAuth")
            
            redirect_url = f"{self.get_base_url()}/auth/callback"
            logger.info(f"URL de callback: {redirect_url}")
            
            response = db.client.auth.sign_in_with_oauth({
                'provider': self.provider,
                'options': {
                    'redirect_to': redirect_url
                }
            })
            
            # Extraer URL de manera robusta
            url = self._extract_url_from_response(response)
            
            if url:
                logger.info(f"URL OAuth generada exitosamente")
                return {'success': True, 'url': url}
            else:
                logger.error("No se pudo extraer URL de la respuesta")
                return {
                    'success': False,
                    'error': 'No se pudo generar URL de autenticación'
                }
                
        except Exception as e:
            logger.error(f"Error generando URL OAuth: {str(e)}")
            return {
                'success': False,
                'error': 'Error al conectar con Google. Verifica la configuración en Supabase Dashboard.'
            }
    
    def _extract_url_from_response(self, response):
        """Extrae la URL de diferentes tipos de respuesta"""
        if hasattr(response, 'url') and response.url:
            return response.url
        elif hasattr(response, 'data') and response.data and hasattr(response.data, 'url'):
            return response.data.url
        elif isinstance(response, dict) and 'url' in response:
            return response['url']
        return None
    
    def handle_callback(self, code):
        """Maneja el callback OAuth y crea/actualiza usuario"""
        try:
            logger.info("Procesando callback OAuth")
            
            if not code:
                return {
                    'success': False,
                    'error': 'Código de autorización requerido',
                    'redirect_url': '/register?error=no_code'
                }
            
            # Intercambiar código por sesión
            response = db.client.auth.exchange_code_for_session({
                'auth_code': code
            })
            
            if not response or not hasattr(response, 'user') or not response.user:
                return {
                    'success': False,
                    'error': 'Error en autenticación',
                    'redirect_url': '/register?error=auth_failed'
                }
            
            user = response.user
            logger.info(f"Usuario autenticado: {user.email}")
            
            # Crear o actualizar usuario en BD
            user_db_id = self._create_or_update_user(user)
            
            # Crear sesión
            self._create_session(user, user_db_id, response.session)
            
            return {
                'success': True,
                'redirect_url': f'/profile/{user_db_id}',
                'user': user
            }
            
        except Exception as e:
            logger.error(f"Error en callback OAuth: {str(e)}")
            return {
                'success': False,
                'error': 'Error en el proceso de autenticación',
                'redirect_url': '/register?error=callback_failed'
            }
    
    def _create_or_update_user(self, user):
        """Crea o actualiza usuario usando cliente autenticado"""
        try:
            # Crear cliente autenticado con el token del usuario
            from supabase import create_client
            import os
            
            # Obtener el cliente con el token de autenticación actual
            auth_client = create_client(
                os.getenv('SUPABASE_URL'),
                os.getenv('SUPABASE_KEY')
            )
            
            # Buscar usuario existente
            user_check = auth_client.table('usuarios').select('id').eq('auth_user_id', user.id).execute()
            
            if user_check.data and len(user_check.data) > 0:
                # Usuario existente
                user_db_id = user_check.data[0]['id']
                logger.info(f"Usuario existente encontrado: {user.email} (ID: {user_db_id})")
                return user_db_id
            
            # Crear nuevo usuario con datos seguros
            new_user = {
                'username': user.email,
                'auth_user_id': user.id,
                'tipo_usuario': 'apicultor',
                'role': 'Apicultor',
                'status': 'active',
                'activo': True,
                'created_at': 'now()'
            }
            
            # Usar el cliente autenticado para insertar
            insert_result = auth_client.table('usuarios').insert(new_user).execute()
            
            if insert_result.data and len(insert_result.data) > 0:
                user_db_id = insert_result.data[0]['id']
                logger.info(f"Usuario creado exitosamente: {user.email} (ID: {user_db_id})")
                
                # Crear info de contacto
                self._create_contact_info_with_client(auth_client, user_db_id, user)
                return user_db_id
            else:
                logger.error("No se pudo crear el usuario - sin datos")
                return str(user.id)  # Fallback
                
        except Exception as e:
            logger.error(f"Error en _create_or_update_user: {str(e)}")
            # Fallback: retornar el auth_user_id
            return str(user.id)
    
    def _create_contact_info(self, user_db_id, user):
        """Crea información de contacto básica para nuevo usuario"""
        try:
            db.client.table('info_contacto').insert({
                'usuario_id': user_db_id,
                'nombre_completo': user.user_metadata.get('full_name', ''),
                'correo_principal': user.email
            }).execute()
        except Exception as e:
            logger.warning(f"Error creando info_contacto: {str(e)}")
    
    def _create_contact_info_with_client(self, client, user_db_id, user):
        """Crea información de contacto usando cliente específico"""
        try:
            client.table('info_contacto').insert({
                'usuario_id': user_db_id,
                'nombre_completo': user.user_metadata.get('full_name', ''),
                'correo_principal': user.email
            }).execute()
        except Exception as e:
            logger.warning(f"Error creando info_contacto: {str(e)}")
    
    def _create_session(self, user, user_db_id, session_data):
        """Crea la sesión de usuario"""
        session['user_id'] = user_db_id
        session['auth_user_id'] = str(user.id)
        session['user_email'] = user.email
        session['user_name'] = user.user_metadata.get('full_name', user.email)
        
        # Almacenar tokens si están disponibles
        if session_data:
            session['access_token'] = session_data.access_token
            if session_data.refresh_token:
                session['refresh_token'] = session_data.refresh_token

# logger = logging.getLogger(__name__)

class AuthManager:
    """Gestor centralizado de autenticación y sesiones de usuario."""
    
    # Cache para cliente autenticado
    _authenticated_client = None
    
    @classmethod
    def get_authenticated_client(cls):
        """
        Única fuente de cliente Supabase autenticado
        Elimina todas las redundancias de búsqueda de tokens
        """
        if cls._authenticated_client is not None:
            return cls._authenticated_client
            
        try:
            # Obtener token de la única fuente confiable
            token = cls._get_auth_token()
            if not token:
                logger.error("No hay token de autenticación disponible")
                return None
                
            # Crear cliente autenticado
            from supabase import create_client
            auth_client = create_client(
                os.getenv('SUPABASE_URL'),
                os.getenv('SUPABASE_KEY')
            )
            auth_client.postgrest.auth(token)
            
            # Verificar que funciona
            auth_client.table('usuarios').select('id').limit(1).execute()
            
            cls._authenticated_client = auth_client
            return auth_client
            
        except Exception as e:
            logger.error(f"Error creando cliente autenticado: {e}")
            return None
    
    @classmethod
    def _get_auth_token(cls):
        """
        Única función para obtener tokens - elimina redundancias
        Orden de prioridad: session → g.user → None
        """
        # 1. Session (prioridad máxima)
        if 'access_token' in session:
            return session['access_token']
            
        # 2. g.user (compatibilidad)
        if hasattr(g, 'user') and g.user and 'access_token' in g.user:
            return g.user['access_token']
            
        return None
    
    @classmethod
    def store_auth_token(cls, access_token, refresh_token=None):
        """Almacena tokens en la única ubicación necesaria"""
        session['access_token'] = access_token
        if refresh_token:
            session['refresh_token'] = refresh_token
    
    @classmethod
    def get_current_user_id(cls):
        """ID de usuario único y consistente"""
        return session.get('user_id') or (g.user.get('id') if hasattr(g, 'user') and g.user else None)
    
    @classmethod
    def is_user_authenticated(cls):
        """Verificación única de autenticación"""
        return cls.get_current_user_id() is not None
    
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
        Carga información del usuario actual usando la autenticación centralizada
        """
        g.user = None
        
        user_id = AuthManager.get_current_user_id()
        if not user_id:
            return
            
        # Usar la información almacenada en session
        g.user = {
            'id': user_id,
            'user_uuid': user_id,
            'name': session.get('user_name'),
            'email': session.get('user_email'),
            'empresa': session.get('user_empresa', ''),
            'access_token': AuthManager._get_auth_token()
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
                .limit(1)\
                .execute()
            
            if user_mapping.data and len(user_mapping.data) > 0:
                user_uuid = user_mapping.data[0]['id']
            else:
                # Si no existe en usuarios, crear uno nuevo
                new_user = {
                    'username': user.email,
                    'auth_user_id': user.id,
                    'tipo_usuario': 'apicultor',
                    'role': 'Apicultor',
                    'status': 'active',
                    'activo': True
                }
                insert_result = db.client.table('usuarios').insert(new_user).execute()
                if insert_result.data:
                    user_uuid = insert_result.data[0]['id']
                    
                    # Crear info de contacto básica
                    try:
                        db.client.table('info_contacto').insert({
                            'usuario_id': user_uuid,
                            'nombre_completo': user.user_metadata.get('full_name', ''),
                            'correo_principal': user.email
                        }).execute()
                    except Exception as e:
                        logger.warning(f"Error creando info_contacto: {str(e)}")
                else:
                    user_uuid = str(user.id)
            
            # Crear sesión de usuario
            session['user_id'] = user_uuid  # ID de la tabla usuarios
            session['auth_user_id'] = str(user.id)  # ID de autenticación
            session['user_email'] = user.email
            session['user_name'] = contact_info.get('nombre_completo') or user.user_metadata.get('full_name', user.email)
            session['user_empresa'] = contact_info.get('nombre_empresa', '')
            
            # Almacenar tokens usando la función centralizada
            if auth_response.session:
                AuthManager.store_auth_token(
                    auth_response.session.access_token,
                    auth_response.session.refresh_token
                )
            
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
    
    # Instancia global de OAuth
    _google_oauth = None
    
    @classmethod
    def get_google_oauth(cls):
        """Obtiene la instancia singleton de GoogleOAuth"""
        if cls._google_oauth is None:
            cls._google_oauth = GoogleOAuth()
        return cls._google_oauth
    
    @staticmethod
    def init_google_auth():
        """Inicia el flujo de autenticación con Google OAuth"""
        return AuthManager.get_google_oauth().generate_auth_url()

    @staticmethod
    def api_google_auth():
        """API endpoint para iniciar el flujo de autenticación con Google OAuth"""
        return AuthManager.get_google_oauth().generate_auth_url()
    
    @staticmethod
    def handle_google_callback(code: str):
        """Maneja el callback de Google OAuth"""
        return AuthManager.get_google_oauth().handle_callback(code)

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
