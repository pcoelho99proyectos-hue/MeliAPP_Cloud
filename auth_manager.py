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
from datetime import datetime, timedelta
import time
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
        """
        Maneja el callback OAuth con verificación de email.
        
        Este método ahora sigue el mismo flujo de verificación que el registro manual:
        1. Verifica que el email esté confirmado por el proveedor (Google)
        2. Usa initialize_user_tables_on_confirmation para crear las tablas
        3. Solo crea sesión si el email está verificado
        """
        try:
            logger.info("=== INICIO CALLBACK OAUTH GOOGLE ===")
            
            if not code:
                logger.error("❌ Código de autorización faltante")
                return {
                    'success': False,
                    'error': 'Código de autorización requerido',
                    'redirect_url': '/register?error=no_code'
                }
            
            # Intercambiar código por sesión
            logger.info("🔄 Intercambiando código por sesión...")
            response = db.client.auth.exchange_code_for_session({
                'auth_code': code
            })
            
            if not response or not hasattr(response, 'user') or not response.user:
                logger.error("❌ Error en respuesta de autenticación")
                return {
                    'success': False,
                    'error': 'Error en autenticación',
                    'redirect_url': '/register?error=auth_failed'
                }
            
            user = response.user
            logger.info(f"👤 Usuario OAuth recibido: {user.email}")
            logger.info(f"📧 Email verificado por proveedor: {user.email_confirmed_at is not None}")
            
            # VERIFICACIÓN CRÍTICA: El email debe estar verificado por el proveedor OAuth
            if not user.email_confirmed_at:
                logger.error(f"❌ Email no verificado por proveedor OAuth: {user.email}")
                return {
                    'success': False,
                    'error': 'El email no ha sido verificado por el proveedor de autenticación',
                    'redirect_url': '/register?error=email_not_verified'
                }
            
            logger.info(f"✅ Email verificado por {self.provider.upper()}: {user.email}")
            
            # Verificar si el usuario ya existe en nuestras tablas
            auth_user_id = str(user.id)
            user_check = db.client.table('usuarios')\
                .select('auth_user_id')\
                .eq('auth_user_id', auth_user_id)\
                .maybe_single()\
                .execute()
            
            if user_check and user_check.data:
                # Usuario existente - solo crear sesión
                logger.info(f"👤 Usuario existente encontrado: {user.email}")
                self._create_session(user, auth_user_id, response.session)
                
                return {
                    'success': True,
                    'redirect_url': '/',
                    'user': user
                }
            else:
                # Usuario nuevo - usar el mismo método de inicialización que el registro manual
                logger.info(f"🆕 Usuario nuevo de OAuth, inicializando tablas...")
                
                user_metadata = user.user_metadata or {}
                initialization_success = AuthManager.initialize_user_tables_on_confirmation(
                    auth_user_id,
                    user.email,
                    user_metadata
                )
                
                if initialization_success:
                    logger.info(f"✅ Tablas de usuario OAuth inicializadas exitosamente: {user.email}")
                    
                    # Crear sesión después de inicialización exitosa
                    self._create_session(user, auth_user_id, response.session)
                    
                    return {
                        'success': True,
                        'redirect_url': '/edit-profile',
                        'user': user
                    }
                else:
                    logger.error(f"❌ Error inicializando tablas para usuario OAuth: {user.email}")
                    return {
                        'success': False,
                        'error': 'Error al crear el perfil de usuario',
                        'redirect_url': '/register?error=initialization_failed'
                    }
            
        except Exception as e:
            logger.error(f"❌ Excepción en callback OAuth: {str(e)}")
            return {
                'success': False,
                'error': 'Error en el proceso de autenticación',
                'redirect_url': '/register?error=callback_failed'
            }
    
    def _create_or_update_user(self, user):
        """Método único y corregido: Crea o actualiza usuario usando el cliente de Supabase"""
        try:
            auth_user_id = str(user.id)
            
            # Buscar usuario existente usando el cliente de db
            user_check = db.client.table('usuarios')\
                .select('auth_user_id')\
                .eq('auth_user_id', auth_user_id)\
                .maybe_single()\
                .execute()
            
            if user_check and hasattr(user_check, 'data') and user_check.data:
                logger.info(f"Usuario existente encontrado: {user.email} (auth_user_id: {auth_user_id})")
                return auth_user_id
            
            # Crear nuevo usuario con datos mínimos para evitar RLS
            user_metadata = user.user_metadata or {}
            new_user = {
                'auth_user_id': auth_user_id,
                'username': user_metadata.get('full_name', user.email.split('@')[0]),  # Username = nombre completo
                'tipo_usuario': 'regular',
                'role': user_metadata.get('role', 'regular'),
                'status': 'activo',
                'activo': True,
                'fecha_registro': 'now()',
                'last_login': 'now()'
            }
            
            # Usar cliente de db para insertar
            insert_result = db.client.table('usuarios').insert(new_user).execute()
            
            if insert_result and hasattr(insert_result, 'data') and insert_result.data and len(insert_result.data) > 0:
                logger.info(f"Usuario creado exitosamente: {user.email} (auth_user_id: {auth_user_id})")
                
                # Crear info de contacto básica según esquema BD
                try:
                    db.client.table('info_contacto').insert({
                        'auth_user_id': auth_user_id,
                        'correo_principal': user.email,
                        'nombre_completo': user.user_metadata.get('full_name', user.email.split('@')[0])
                    }).execute()
                except Exception as e:
                    logger.warning(f"Error creando info_contacto: {e}")
                
                return auth_user_id
            else:
                logger.error("No se pudo crear el usuario")
                return auth_user_id  # Fallback con auth_user_id
                
        except Exception as e:
            logger.error(f"Error en _create_or_update_user: {str(e)}")
            # Siempre retornar auth_user_id para mantener consistencia
            return str(user.id)
    
    
    def _create_session(self, user, auth_user_id, session_data):
        """Crea la sesión de usuario - método único y simplificado"""
        session['user_id'] = auth_user_id  # user_id = auth_user_id (consistencia)
        session['user_email'] = user.email
        session['user_name'] = user.user_metadata.get('full_name', user.email.split('@')[0])
        
        # Almacenar tokens si están disponibles
        if session_data:
            session['access_token'] = session_data.access_token
            if session_data.refresh_token:
                session['refresh_token'] = session_data.refresh_token

class AuthManager:
    """Gestor centralizado de autenticación y sesiones de usuario."""
    
    # Cache para cliente autenticado
    _authenticated_client = None
    
    @classmethod
    def get_authenticated_client(cls):
        """
        Única fuente de cliente Supabase autenticado
        Simplificado para evitar problemas de cache y refresh
        """
        try:
            # Siempre crear un cliente fresco para evitar problemas de cache
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
            
            logger.info(f"Cliente autenticado creado con token: {token[:20]}...")
            return auth_client
            
        except Exception as e:
            logger.error(f"Error creando cliente autenticado: {e}")
            return None
    
    @classmethod
    def _should_refresh_token(cls):
        """
        Determina si el token debe ser refrescado basado en errores previos
        y en la disponibilidad de un refresh token.
        
        Returns:
            bool: True si el token debe refrescarse, False en caso contrario.
        """
        # Si hay un flag de error de JWT, intentar refrescar
        if session.get('jwt_expired_error', False) and 'refresh_token' in session:
            # Limpiar el flag de error
            session['jwt_expired_error'] = False
            logger.info("Detectado error de JWT expirado, intentando refrescar token")
            return True
        return False
    
    @classmethod
    def _refresh_token(cls):
        """
        Refresca el token de acceso usando el refresh token almacenado.
        
        Returns:
            bool: True si el refresh fue exitoso, False en caso contrario.
        """
        try:
            if 'refresh_token' not in session:
                logger.error("No hay refresh token disponible para refrescar la sesión")
                return False
                
            refresh_token = session['refresh_token']
            
            # Intentar refrescar la sesión usando la API de Supabase
            refresh_response = db.client.auth.refresh_session(refresh_token)
            
            if refresh_response and hasattr(refresh_response, 'session'):
                # Guardar los nuevos tokens
                session['access_token'] = refresh_response.session.access_token
                if refresh_response.session.refresh_token:
                    session['refresh_token'] = refresh_response.session.refresh_token
                    
                logger.info("Token refrescado exitosamente")
                return True
            else:
                logger.error("No se pudo refrescar el token: respuesta inválida")
                return False
                
        except Exception as e:
            logger.error(f"Error al refrescar token: {str(e)}")
            return False
    
    @classmethod
    def _get_auth_token(cls):
        """
        Única función para obtener tokens - elimina redundancias
        Orden de prioridad: session → g.user → None
        Intenta refrescar el token si es necesario.
        """
        # Verificar si necesitamos refrescar el token
        if cls._should_refresh_token():
            # Intentar refrescar el token
            cls._refresh_token()
            
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
                return redirect(url_for('auth.login'))
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
        
        # Obtener username desde la tabla usuarios
        username = None
        try:
            from supabase_client import SupabaseClient
            supabase = SupabaseClient()
            usuario_response = supabase.client.table('usuarios').select('username').eq('auth_user_id', user_id).single().execute()
            if usuario_response.data:
                username = usuario_response.data.get('username')
        except Exception as e:
            logger.warning(f"No se pudo obtener username para user_id {user_id}: {e}")
            
        # Usar la información almacenada en session y username de la base de datos
        g.user = {
            'id': user_id,
            'user_uuid': user_id,
            'name': session.get('user_name'),
            'email': session.get('user_email'),
            'empresa': session.get('user_empresa', ''),
            'username': username,
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
                .eq('auth_user_id', user.id)\
                .execute()
            
            contact_info = contact_response.data[0] if contact_response.data else {}
            
            # Buscar el usuario en la tabla usuarios por auth_user_id (PRIMARY KEY)
            user_mapping = db.client.table('usuarios')\
                .select('auth_user_id')\
                .eq('auth_user_id', user.id)\
                .limit(1)\
                .execute()
            
            if user_mapping.data and len(user_mapping.data) > 0:
                auth_user_id = user_mapping.data[0]['auth_user_id']
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
                    auth_user_id = insert_result.data[0]['auth_user_id']
                    
                    # Crear info de contacto básica
                    try:
                        db.client.table('info_contacto').insert({
                            'auth_user_id': auth_user_id,
                            'nombre_completo': user.user_metadata.get('full_name', ''),
                            'correo_principal': user.email
                        }).execute()
                    except Exception as e:
                        logger.warning(f"Error creando info_contacto: {str(e)}")
                else:
                    auth_user_id = str(user.id)
            
            # Crear sesión de usuario
            session['user_id'] = auth_user_id  # auth_user_id es ahora la PRIMARY KEY
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
    def change_user_password(current_password: str, new_password: str):
        """
        Cambia la contraseña de un usuario autenticado.
        Verifica la contraseña actual antes de realizar el cambio.
        """
        if 'user_id' not in session or 'user_email' not in session:
            return {"success": False, "error": "Usuario no autenticado", "status_code": 401}

        if not new_password or len(new_password) < 6:
            return {"success": False, "error": "La nueva contraseña debe tener al menos 6 caracteres", "status_code": 400}

        user_email = session.get('user_email')

        try:
            # 1. Verificar la contraseña actual intentando iniciar sesión con ella.
            test_auth_response = db.client.auth.sign_in_with_password({
                "email": user_email,
                "password": current_password
            })

            if not test_auth_response.user:
                return {"success": False, "error": "La contraseña actual es incorrecta", "status_code": 401}

            # 2. Si la contraseña es correcta, usar el cliente autenticado de la sesión actual para actualizar.
            update_response = db.client.auth.update_user({"password": new_password})

            if update_response.user:
                logger.info(f"Contraseña actualizada exitosamente para el usuario {user_email}")
                return {"success": True, "message": "Contraseña actualizada exitosamente."}
            else:
                logger.error(f"Error al actualizar la contraseña para {user_email}: Respuesta inesperada de Supabase.")
                return {"success": False, "error": "No se pudo actualizar la contraseña. Inténtalo de nuevo.", "status_code": 500}

        except Exception as e:
            error_str = str(e)
            logger.error(f"Excepción al cambiar la contraseña para {user_email}: {error_str}")
            if 'Invalid login credentials' in error_str:
                return {"success": False, "error": "La contraseña actual es incorrecta", "status_code": 401}
            
            return {"success": False, "error": "Ocurrió un error inesperado en el servidor.", "status_code": 500}

    @staticmethod
    def logout_user():
        """Cierra la sesión del usuario actual."""
        session.clear()
        return {
            "success": True,
            "redirect_url": "/login"
        }
    
    # Cache para rate limiting de registro - estructura: {email: {'attempts': count, 'first_attempt': timestamp}}
    _registration_attempts = {}
    
    @staticmethod
    def _check_registration_rate_limit(email: str) -> tuple[bool, str]:
        """
        Verifica si el email puede registrarse (rate limiting: 3 intentos en 15 minutos)
        
        Returns:
            tuple: (can_register: bool, error_message: str)
        """
        current_time = time.time()
        
        if email in AuthManager._registration_attempts:
            attempt_data = AuthManager._registration_attempts[email]
            first_attempt = attempt_data['first_attempt']
            attempts_count = attempt_data['attempts']
            time_diff = current_time - first_attempt
            
            # Si han pasado más de 15 minutos, resetear contador
            if time_diff >= 900:  # 15 minutos = 900 segundos
                AuthManager._registration_attempts[email] = {'attempts': 1, 'first_attempt': current_time}
                return True, ""
            
            # Si ya se hicieron 3 intentos en los últimos 15 minutos
            if attempts_count >= 3:
                remaining_minutes = int((900 - time_diff) / 60) + 1
                return False, f"Has excedido el límite de 3 intentos de registro. Debes esperar {remaining_minutes} minutos antes de intentar nuevamente"
            
            # Incrementar contador de intentos
            AuthManager._registration_attempts[email]['attempts'] += 1
        else:
            # Primer intento para este email
            AuthManager._registration_attempts[email] = {'attempts': 1, 'first_attempt': current_time}
        
        # Limpiar intentos antiguos (más de 15 minutos)
        expired_emails = []
        for cached_email, cached_data in AuthManager._registration_attempts.items():
            if current_time - cached_data['first_attempt'] > 900:
                expired_emails.append(cached_email)
        
        for expired_email in expired_emails:
            del AuthManager._registration_attempts[expired_email]
        
        return True, ""
    
    @staticmethod
    def initialize_user_tables_on_confirmation(auth_user_id, email, user_metadata):
        """
        Inicializa las tablas de usuario cuando se confirma el email.
        Usa función de base de datos para bypasear RLS correctamente.
        """
        try:
            from supabase_client import db
            
            full_name = user_metadata.get('full_name', email.split('@')[0])
            company = user_metadata.get('company', '')
            role = user_metadata.get('role', 'regular')
            
            logger.info(f"Inicializando tablas para usuario confirmado: {email}")
            logger.info(f"Datos: full_name='{full_name}', company='{role}'")
            
            # Llamar a la función de base de datos que bypasea RLS
            result = db.client.rpc('initialize_new_user', {
                'p_auth_user_id': auth_user_id,
                'p_email': email,
                'p_username': full_name,
                'p_tipo_usuario': role,
                'p_role': role,
                'p_nombre_completo': full_name,
                'p_nombre_empresa': company if company else None
            }).execute()
            
            logger.info(f"Respuesta de función DB: {result.data}")
            
            if result.data and result.data.get('success'):
                logger.info(f"✅ Inicialización completa exitosa para: {email}")
                return True
            else:
                error_msg = result.data.get('message', 'Error desconocido') if result.data else 'Sin respuesta'
                logger.error(f"❌ Error en función DB: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error inicializando tablas para usuario {email}: {str(e)}")
            logger.error(f"Detalles del error: {type(e).__name__}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False


    @staticmethod
    def verify_email_confirmation(token_hash: str, type_param: str = 'email'):
        """
        Verifica el token de confirmación de email y inicializa las tablas del usuario.
        
        Args:
            token_hash: Hash del token de confirmación
            type_param: Tipo de verificación (default: 'email')
        
        Returns:
            tuple: (success: bool, message: str, user_data: dict)
        """
        try:
            # Verificar el token con Supabase
            verify_result = db.client.auth.verify_otp({
                'token_hash': token_hash,
                'type': type_param
            })
            
            if not verify_result.user:
                logger.error("Token de confirmación inválido o expirado")
                return False, "Token de confirmación inválido o expirado", {}
            
            user = verify_result.user
            logger.info(f"Email confirmado exitosamente para usuario: {user.email}")
            
            # Inicializar tablas del usuario
            user_metadata = user.user_metadata or {}
            initialization_success = AuthManager.initialize_user_tables_on_confirmation(
                user.id, 
                user.email, 
                user_metadata
            )
            
            if initialization_success:
                logger.info(f"Usuario {user.email} completamente inicializado")
                return True, "Email confirmado y usuario inicializado exitosamente", {
                    'user_id': user.id,
                    'email': user.email,
                    'user_metadata': user_metadata
                }
            else:
                logger.warning(f"Email confirmado pero falló la inicialización para {user.email}")
                return True, "Email confirmado pero hubo problemas en la inicialización", {
                    'user_id': user.id,
                    'email': user.email,
                    'user_metadata': user_metadata
                }
                
        except Exception as e:
            logger.error(f"Error verificando confirmación de email: {str(e)}")
            return False, f"Error verificando confirmación: {str(e)}", {}

    @staticmethod
    def resend_confirmation_email(email: str):
        """
        Reenvía el email de confirmación para un usuario.
        
        Args:
            email: Email del usuario
        
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            result = db.client.auth.resend({
                'type': 'signup',
                'email': email
            })
            
            logger.info(f"Email de confirmación reenviado a: {email}")
            return True, "Email de confirmación enviado exitosamente"
            
        except Exception as e:
            logger.error(f"Error reenviando email de confirmación a {email}: {str(e)}")
            return False, f"Error enviando email: {str(e)}"

    
    @staticmethod
    def request_password_reset(email: str):
        """Envía un correo de reseteo de contraseña utilizando Supabase."""
        if not email:
            return {"success": False, "error": "El correo es requerido", "status_code": 400}
        
        try:
            # Aquí no se necesita redirect_to porque Supabase usará la URL configurada en el dashboard
            # En esta versión de la librería, la llamada es a través de 'api'
            db.client.auth.api.reset_password_for_email(email)
            logger.info(f"Solicitud de reseteo de contraseña enviada para: {email}")
            return {"success": True, "message": "Si el correo está registrado, recibirás un enlace para recuperar tu contraseña."}
        except Exception as e:
            # Por seguridad, no revelamos si el correo existe o no.
            # Logueamos el error real pero devolvemos un mensaje genérico.
            logger.error(f"Error al solicitar reseteo de contraseña para {email}: {str(e)}")
            return {"success": True, "message": "Si el correo está registrado, recibirás un enlace para recuperar tu contraseña."}

    @staticmethod
    def request_password_reset_authenticated():
        """Solicita un reseteo de contraseña para el usuario autenticado actual."""
        if 'user_email' not in session:
            return {"success": False, "error": "Usuario no autenticado", "status_code": 401}
        
        email = session['user_email']
        return AuthManager.request_password_reset(email)

    @staticmethod
    def register_user(email: str, password: str, full_name: str, company: str = "", role: str = "regular"):
        """
        Registra un nuevo usuario usando modify_DB.py centralizadamente.
        
        Args:
            email: Email del usuario
            password: Contraseña del usuario
            full_name: Nombre completo del usuario
            company: Nombre de la empresa (opcional)
            
        Returns:
            dict: Resultado del registro
        """
        try:
            logger.info("=== INICIO REGISTER_USER ===")
            logger.info(f"Email: {email}, Full name: {full_name}, Company: {company}")
            
            # Verificar rate limiting
            can_register, rate_limit_error = AuthManager._check_registration_rate_limit(email)
            if not can_register:
                logger.warning(f"Rate limit alcanzado para {email}: {rate_limit_error}")
                return {
                    "success": False,
                    "error": rate_limit_error,
                    "status_code": 429
                }
            
            # Validaciones básicas
            if not email or not password or not full_name:
                logger.error("Faltan campos requeridos")
                return {
                    "success": False,
                    "error": "Todos los campos son requeridos",
                    "status_code": 400
                }
            
            if len(password) < 6:
                logger.error("Contraseña muy corta")
                return {
                    "success": False,
                    "error": "La contraseña debe tener al menos 6 caracteres",
                    "status_code": 400
                }
            
            # Obtener BASE_URL para el callback de confirmación
            from app import get_base_url
            base_url = get_base_url()
            callback_url = f"{base_url}/auth/confirm"
            
            logger.info(f"BASE_URL: {base_url}")
            logger.info(f"Callback URL: {callback_url}")
            
            # SIEMPRE usar confirmación de email con PKCE
            logger.info("=" * 60)
            logger.info("📧 MODO: Confirmación de email ACTIVADA (Resend)")
            logger.info(f"📧 Callback URL: {callback_url}")
            logger.info("=" * 60)
            
            # Preparar opciones de sign_up con email redirect
            signup_options = {
                "data": {
                    "full_name": full_name,
                    "company": company,
                    "email": email,
                    "role": role
                },
                "email_redirect_to": callback_url
            }
            
            logger.info(f"Creando usuario en Supabase Auth con confirmación de email")
            
            try:
                auth_response = db.client.auth.sign_up({
                    "email": email,
                    "password": password,
                    "options": signup_options
                })
                
                logger.info(f"✅ Usuario creado exitosamente en Supabase Auth")
                logger.info(f"Respuesta de Supabase Auth: {auth_response}")
                
            except Exception as signup_error:
                error_msg = str(signup_error)
                
                # Detectar rate limiting específicamente
                if "rate limit" in error_msg.lower() or "429" in error_msg:
                    logger.error("=" * 60)
                    logger.error("🚫 RATE LIMIT EXCEEDED")
                    logger.error(f"Error: {error_msg}")
                    logger.error("=" * 60)
                    logger.error("SOLUCIONES:")
                    logger.error("1. Esperar 1 hora")
                    logger.error("2. Usar email diferente")
                    logger.error("3. Dashboard Supabase → Auth → Rate Limits → Aumentar límite")
                    logger.error("=" * 60)
                    
                    return {
                        "success": False,
                        "error": "Has alcanzado el límite de intentos de registro. Espera 1 hora o usa un email diferente.",
                        "status_code": 429
                    }
                
                # Manejar errores específicos
                if "confirmation email" in error_msg.lower() or "sending" in error_msg.lower():
                    logger.error("=" * 60)
                    logger.error("🚨 ERROR ENVIANDO EMAIL DE CONFIRMACIÓN")
                    logger.error(f"Error: {error_msg}")
                    logger.error("=" * 60)
                    logger.error("POSIBLES CAUSAS:")
                    logger.error("1. SMTP no configurado correctamente en Supabase")
                    logger.error("2. API Key de Resend inválida")
                    logger.error("3. Confirmar que 'Confirm email' está ON en Dashboard")
                    logger.error("=" * 60)
                    
                    return {
                        "success": False,
                        "error": "Error al enviar email de confirmación. Verifica configuración SMTP en Supabase Dashboard.",
                        "status_code": 500
                    }
                else:
                    logger.error(f"❌ Error crítico en sign_up: {error_msg}")
                    raise
            
            if auth_response.user:
                auth_user_id = auth_response.user.id
                logger.info(f"✅ Usuario creado en Auth con ID: {auth_user_id}")
                
                # Usuario creado - Debe confirmar email antes de poder usar la app
                logger.info(f"📧 Email de confirmación enviado a: {email}")
                logger.info("📧 Usuario debe confirmar su email antes de poder iniciar sesión")
                logger.info("📧 Las tablas de usuario se crearán después de confirmar el email")
                
                return {
                    "success": True,
                    "message": "¡Registro exitoso! Por favor revisa tu correo electrónico y haz clic en el enlace de confirmación para activar tu cuenta.",
                    "status_code": 200,
                    "auth_user_id": auth_user_id,
                    "requires_confirmation": True
                }
            else:
                logger.error("No se pudo crear el usuario en Supabase Auth")
                return {
                    "success": False,
                    "error": "Error al crear usuario en el sistema de autenticación",
                    "status_code": 500
                }
            
        except Exception as e:
            logger.error(f"Excepción en register_user: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": "Error interno al crear cuenta",
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