"""
Módulo de rutas web para MeliAPP_v2.

Este módulo contiene TODAS las rutas web que devuelven HTML:
- Página principal (home)
- Páginas de autenticación (login, register)
- Páginas de prueba y utilidades
- Logout (con llamada a API REST)

IMPORTANTE: La lógica de autenticación se maneja en auth_manager_routes.py con API REST.
Este módulo solo sirve páginas HTML y el logout ejecuta la API REST en el servidor.
"""

import logging
from flask import Blueprint, render_template, session, redirect

logger = logging.getLogger(__name__)

# Crear blueprint para todas las rutas web
web_bp = Blueprint('web', __name__)

# ====================
# Páginas Generales
# ====================

@web_bp.route('/')
def home():
    """
    Página principal con diseño moderno y llamadas a la acción.
    
    GET /
    """
    return render_template('pages/home.html')

@web_bp.route('/auth-test')
def auth_test():
    """
    Página de prueba para las rutas de autenticación API.
    
    GET /auth-test
    """
    return render_template('pages/auth_test.html')

# ====================
# Páginas de Autenticación
# ====================

@web_bp.route('/login')
def login():
    """
    Sirve la página HTML de login.
    
    GET /login
    
    La lógica de autenticación se maneja vía JavaScript llamando a POST /api/auth/login
    """
    return render_template('pages/login.html')

@web_bp.route('/register')
def register():
    """
    Sirve la página HTML de registro.
    
    GET /register
    
    La lógica de registro se maneja vía JavaScript llamando a POST /api/auth/register
    """
    return render_template('pages/register.html')

@web_bp.route('/logout')
def logout():
    """
    Cierra sesión del usuario y redirige al home.
    
    GET /logout
    
    Esta ruta web ejecuta session.clear() directamente en el servidor.
    """
    try:
        session.clear()
        logger.info("Sesión cerrada exitosamente (web)")
        return redirect('/')
    except Exception as e:
        logger.error(f"Error en logout web: {str(e)}")
        return redirect('/')

@web_bp.route('/edit-profile')
def edit_profile():
    """
    Página de edición de perfil para usuarios autenticados.
    
    GET /edit-profile
    
    Requiere autenticación. La actualización de datos se maneja vía API REST.
    """
    from auth_manager import AuthManager
    from supabase_client import db
    
    # Verificar autenticación manualmente
    auth_user_id = session.get('user_id')
    if not auth_user_id:
        logger.warning("Usuario no autenticado intentó acceder a /edit-profile")
        return redirect('/login')
    
    # Obtener información de ubicación del usuario
    user_location = {'region': None, 'comuna': None}
    try:
        contact_info_response = db.client.table('info_contacto')\
            .select('region, comuna')\
            .eq('auth_user_id', auth_user_id)\
            .maybe_single()\
            .execute()
        
        if contact_info_response.data:
            user_location['region'] = contact_info_response.data.get('region')
            user_location['comuna'] = contact_info_response.data.get('comuna')
    except Exception as e:
        logger.warning(f"No se pudo obtener info_contacto para {auth_user_id}: {e}")
    
    return render_template('pages/edit_profile.html', 
                         user_id=auth_user_id, 
                         user_location=user_location)

# ====================
# OAuth Callback
# ====================

@web_bp.route('/auth/callback')
def oauth_callback():
    """
    Callback de OAuth Google.
    
    GET /auth/callback
    
    Google redirige aquí con tokens en el fragmento (#) de la URL.
    Esta página HTML extrae los tokens con JavaScript y los envía al API.
    """
    # Renderizar página que maneja tokens en fragmento
    return render_template('auth/oauth-callback.html')
