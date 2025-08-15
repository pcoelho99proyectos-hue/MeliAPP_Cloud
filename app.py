import logging
from flask import Flask, request
from datetime import datetime
import os
from dotenv import load_dotenv
import sys
import io
from supabase_client import db

# Load environment variables
load_dotenv()

# Desactivar logs de hpack y httpcore
logging.getLogger('hpack').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

# Configuración de logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Configuración de la aplicación
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'meliapp-secret-key-change-in-production')

# Configuración CRÍTICA para persistencia de sesión
app.config.update(
    SESSION_COOKIE_SECURE=False,  # Cambiar a True en producción HTTPS
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',  # Permite cookies en navegación normal
    SESSION_COOKIE_NAME='meliapp_session',
    PERMANENT_SESSION_LIFETIME=3600 * 1,  # 1 hora
)

# Configuración
DEBUG = False  # Siempre False para producción
PORT = int(os.environ.get('PORT', 3000))

# Configuración para producción
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False
app.json.sort_keys = False

# Filtro para formatear fechas en las plantillas
@app.template_filter('datetimeformat')
def datetimeformat(value, format='%d/%m/%Y %H:%M'):
    if value is None:
        return ""
    if isinstance(value, str):
        # Si es un string, intentar convertirlo a datetime
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return value
    return value.strftime(format)

# Cargar información del usuario actual en cada request
from auth_manager import AuthManager

@app.before_request
def load_user():
    """Carga la información del usuario actual en g.user para todas las peticiones."""
    AuthManager.load_current_user()
# ====================
# Configuración de Blueprints
# ====================

from routes import api_bp, web_bp
from edit_user_data import edit_bp
from debug_endpoint import debug_bp

# Registrar blueprints
app.register_blueprint(api_bp)
app.register_blueprint(web_bp)
app.register_blueprint(edit_bp)
app.register_blueprint(debug_bp)

def list_routes():
    """
    Muestra todas las rutas registradas en la aplicación con sus métodos HTTP.
    Agrupadas por categorías para mejor legibilidad.
    """
    # Agrupar rutas por categoría
    api_routes = []
    web_routes = []
    
    for rule in app.url_map.iter_rules():
        methods = sorted([m for m in rule.methods if m not in ('OPTIONS', 'HEAD')])
        route_path = str(rule)
        route_info = {
            'endpoint': rule.endpoint,
            'path': route_path,
            'methods': methods
        }
        
        if route_path.startswith('/api/'):
            api_routes.append(route_info)
        else:
            web_routes.append(route_info)
    
    # Generar salida formateada
    output = []
    
    # 1. Rutas web
    output.append("\n=== RUTAS WEB ===")
    for route in sorted(web_routes, key=lambda x: x['path']):
        methods = ','.join(route['methods'])
        output.append(f"{route['path']:50} [{methods:10}]")
    
    # 2. Rutas API
    output.append("\n=== RUTAS API ===")
    for route in sorted(api_routes, key=lambda x: x['path']):
        methods = ','.join(route['methods'])
        output.append(f"{route['path']:50} [{methods:10}]")
    
    return '\n'.join(output)

def get_base_url():
    """
    Función centralizada para obtener la URL base de la aplicación.
    Detecta automáticamente el entorno (desarrollo/producción).
    """
    # Prioridad 1: BASE_URL explícito
    base_url = os.getenv('BASE_URL')
    if base_url:
        return base_url.rstrip('/')
    
    # Prioridad 2: Site URL personalizada
    site_url = os.getenv('NEXT_PUBLIC_SITE_URL')
    if site_url:
        return site_url.rstrip('/')
    
    # Prioridad 3: Dominio personalizado para producción
    custom_domain = "meli-app-v3.vercel.app"
    if os.getenv('VERCEL') == '1':
        return f"https://{custom_domain}"
    
    # Prioridad 4: VERCEL_URL (fallback)
    vercel_url = os.getenv('VERCEL_URL')
    if vercel_url:
        return f"https://{vercel_url}"
    
    # Prioridad 5: Detectar desde request
    try:
        from flask import request
        scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
        host = request.headers.get('X-Forwarded-Host', request.host)
        
        # Forzar dominio personalizado en producción
        if 'vercel.app' in host:
            return "https://meli-app-v3.vercel.app"
        
        return f"{scheme}://{host}"
    except RuntimeError:
        return f"http://127.0.0.1:{PORT}"

def print_welcome_message():
    """Muestra un mensaje de bienvenida completo con información de todos los endpoints."""
    base_url = get_base_url()
    welcome_msg = f"""
=== 🍯 MELI APP v3.0 - INFORMACIÓN COMPLETA ===

📊 **ESTADO DEL SISTEMA:**
✅ Conexión con Supabase establecida
✅ Todos los módulos cargados correctamente
✅ Blueprints registrados: api_bp, web_bp
✅ Autenticación con Supabase Auth activa

🌐 **ENDPOINTS DISPONIBLES:**

[🏠 RUTAS WEB - INTERFAZ DE USUARIO]
/                            - Página principal (Home)
/login                       - Formulario de inicio de sesión
/register                    - Formulario de registro
/profile/<user_id>           - Perfil de usuario público
/edit-profile               - Editar perfil (requiere login)
/search                     - Búsqueda de usuarios
/buscar                     - Búsqueda avanzada
/gestionar-lote             - Gestión de lotes de producción
/auth-test                  - Página de prueba de autenticación
/logout                     - Cerrar sesión

[🔧 RUTAS DEBUG]
/debug/oauth               - Página de prueba OAuth
/debug/info_contacto/<uuid:usuario_uuid> - Ver info de contacto
/debug/test_update/<uuid:usuario_uuid>   - Prueba de actualización

[📋 RUTAS API]
/api/tables                - Listar todas las tablas
/api/table/<table_name>    - Datos de tabla específica
/api/test                  - Endpoint de prueba
/api/test-db               - Prueba de conexión DB
/api/usuario/<uuid>        - Datos de usuario
/api/usuario/<uuid>/qr     - QR de usuario
/api/user/current          - Usuario actual

[🔐 RUTAS AUTH API]
/api/auth/login            - Login API
/api/auth/register         - Registro API
/api/auth/logout           - Logout API
/api/auth/session          - Estado de sesión
/api/auth/google           - Google OAuth

[📊 TABLAS DISPONIBLES EN API]
- usuarios
- info_contacto  
- ubicaciones
- produccion_apicola
- origenes_botanicos
- solicitudes_apicultor

[🔐 SISTEMA DE AUTENTICACIÓN]
- Login con Supabase Auth (email/contraseña)
- Registro con validación de email
- Integración con Google OAuth
- Mapeo auth_user_id ↔ usuarios.uuid
- Gestión de sesiones con Flask

[⚙️ CONFIGURACIÓN]
- Puerto: {PORT}
- Debug: {DEBUG}
- Base de datos: Supabase PostgreSQL
- Framework: Flask con Blueprints
- Autenticación: Supabase Auth

🚀 **SERVIDOR INICIADO**
Accede a: {base_url}
"""
    print(welcome_msg)

def init_google_oauth_flow(is_api=False):
    """Inicializa el flujo de autenticación con Google OAuth usando detección universal."""
    try:
        current_app.logger.info(f"Iniciando init_google_oauth_flow - is_api: {is_api}")
        
        # Usar función centralizada para obtener URL base
        base_url = get_base_url()
        redirect_uri = f"{base_url}/auth/callback"
        
        current_app.logger.info(f"URL base detectada: {base_url}")
        current_app.logger.info(f"URL de redirección: {redirect_uri}")
        
        # Usar el cliente de Supabase para generar la URL de autorización
        auth_response = db.auth.sign_in_with_oauth({
            'provider': 'google',
            'options': {
                'redirect_to': redirect_uri,
                'scopes': 'email profile openid'
            }
        })
        
        current_app.logger.info("Respuesta de Supabase auth recibida")
        current_app.logger.info(f"URL generada exitosamente: {auth_response.url}")
        
        return auth_response.url
        
    except Exception as e:
        current_app.logger.error(f"Error en init_google_oauth_flow: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return None

def main():
    """Función principal que inicia la aplicación."""
    try:
        # Configurar la codificación de la consola para Windows (solo local)
        

        # Configurar la salida estándar
        if sys.stdout.encoding != 'utf-8':
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        
        # Verificar la conexión con Supabase al inicio
        db.test_connection()
        print("\n[✅] Conexión con Supabase establecida correctamente")
        
        # Mostrar rutas detalladas
        print("\n=== RUTAS REGISTRADAS ===")
        print(list_routes())
        
        # Mostrar mensaje de bienvenida completo
        print_welcome_message()
        
        # Iniciar la aplicación sin reloader
        print(f"\n🚀 Iniciando servidor en http://127.0.0.1:{PORT}/")
        print("Presiona CTRL+C para salir\n")
        
        app.run(host='0.0.0.0', port=PORT, debug=DEBUG, use_reloader=False)
        
    except Exception as e:
        print(f"\n[❌] Error al iniciar la aplicación: {str(e)}")
        print("Asegúrate de que las credenciales en el archivo .env sean correctas.")

# Para Vercel, exponemos la app directamente
if __name__ == '__main__':
    main()
