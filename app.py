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

# Configuración de logging para producción (sin archivo)
handlers = [logging.StreamHandler()]

# Solo agregar FileHandler en desarrollo local
if os.getenv('VERCEL') != '1' and os.path.exists('.'):
    try:
        handlers.append(logging.FileHandler('meliapp_debug.log', encoding='utf-8'))
    except (OSError, PermissionError):
        # Ignorar si no se puede crear el archivo
        pass

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=handlers
)
logger = logging.getLogger(__name__)

# Habilitar logs específicos para auth y registro
logging.getLogger('auth_manager').setLevel(logging.DEBUG)
logging.getLogger('auth_manager_routes').setLevel(logging.DEBUG)
logging.getLogger('modify_DB').setLevel(logging.DEBUG)

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
DEBUG = True  # Habilitado para debug del registro
PORT = int(os.environ.get('PORT', 3000))

# Log de inicio
logger.info("=" * 70)
logger.info("  🍯 MELIAPP v3.0 - API REST")
logger.info("=" * 70)
logger.info(f"  📍 Puerto: {PORT}")
logger.info(f"  🔧 Debug: {DEBUG}")
logger.info(f"  🌐 Base URL: http://localhost:{PORT}")
logger.info(f"  📱 API REST: Listo para apps móviles (Flutter, React Native)")
logger.info(f"  ✅ Autenticación: Email + OAuth Google")
logger.info(f"  📧 Verificación: Activada (Resend)")
logger.info(f"  🔐 Sesión: Cookies HTTP-only")
logger.info("=" * 70)
logger.info("  Endpoints principales:")
logger.info("    • POST /api/auth/register - Registro con verificación")
logger.info("    • POST /api/auth/login - Login")
logger.info("    • GET  /api/auth/session - Verificar sesión")
logger.info("    • POST /api/auth/google - OAuth Google")
logger.info("    • GET  /api/profile/me - Perfil completo")
logger.info("    • POST /api/edit/usuarios - Editar usuario")
logger.info("    • GET  /api/lotes/{uuid} - Obtener lotes")
logger.info("=" * 70)
logger.info("  📚 Documentación: /docs/API_REST_VERIFICACION.md")
logger.info("  🧪 Testing: Ver ejemplos con curl en documentación")
logger.info("=" * 70)

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

from auth_manager_routes import auth_bp
from edit_user_data import edit_bp
from botanical_chart import botanical_bp
from supabase_client_routes import supabase_bp
from searcher_routes import search_bp, search_web_bp
from data_tables_routes import data_tables_bp
from lotes_routes import lotes_api_bp, lotes_web_bp, lotes_debug_bp
from web_routes import web_bp  # Contiene TODAS las rutas web (home, login, register, logout)
from profile_routes import profile_bp

# Registrar blueprints
app.register_blueprint(web_bp)  # Rutas web (HTML): /, /login, /register, /logout
app.register_blueprint(auth_bp)  # API REST de autenticación: /api/auth/*
app.register_blueprint(botanical_bp)
app.register_blueprint(supabase_bp)
app.register_blueprint(search_bp)
app.register_blueprint(search_web_bp)
app.register_blueprint(data_tables_bp)
app.register_blueprint(lotes_api_bp)
app.register_blueprint(lotes_web_bp)
app.register_blueprint(lotes_debug_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(edit_bp)

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
    custom_domain = "meliapp-cloud.vercel.app"
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
            return "https://meliapp-cloud.vercel.app"
        
        return f"{scheme}://{host}"
    except RuntimeError:
        return f"http://127.0.0.1:{PORT}"

def print_welcome_message():
    """Muestra un mensaje de bienvenida completo con la arquitectura actual del proyecto."""
    base_url = get_base_url()
    welcome_msg = f"""
=== 🍯 MELI APP CLOUD - ARQUITECTURA ACTUALIZADA ===

📊 **ESTADO DEL SISTEMA:**
✅ Conexión con Supabase establecida
✅ Módulos cargados: auth_manager, supabase_client, botanical_chart
✅ Blueprints activos: api_bp, web_bp, edit_bp, debug_bp, botanical_bp
✅ Autenticación: Google OAuth + Supabase Auth
✅ Sistema de QR codes operativo
✅ Clasificación botánica visual activa

🌐 **ARQUITECTURA ACTUALIZADA:**

[🏗️ STACK TECNOLÓGICO]
- Backend: Flask 2.3.3 con Blueprints modulares
- Base de datos: Supabase (PostgreSQL)
- Frontend: HTML5 + Tailwind CSS + JavaScript vanilla
- Autenticación: Supabase Auth + Google OAuth
- QR: segno library para generación dinámica
- Despliegue: Vercel-ready

[📁 ESTRUCTURA DE ARCHIVOS]
├── app.py                          # Aplicación principal
├── auth_manager.py                 # Gestión centralizada de autenticación
├── supabase_client.py             # Cliente singleton Supabase
├── searcher.py                    # Búsqueda avanzada multi-tabla
├── botanical_chart.py             # Sistema de clasificación botánica
├── data_tables_supabase.py        # Operaciones de tablas
├── routes.py                      # Endpoints API REST
├── edit_user_data.py              # Edición de usuarios
├── modify_DB.py                   # Modificaciones de BD
├── gmaps_utils.py                 # Utilidades Google Maps
├── debug_endpoint.py              # Endpoints de debug
├── qr_code/                       # Módulo de generación QR
├── static/                        # Archivos estáticos
├── templates/                     # Plantillas modulares
└── docs/                          # Documentación

[🚀 ENDPOINTS DISPONIBLES:]

[🏠 RUTAS WEB - INTERFAZ RESPONSIVE]
/                            - Página principal con búsqueda
/login                       - Login con Google OAuth
/register                    - Registro de nuevos usuarios
/profile/<uuid>              - Perfil público con QR
/editar-perfil               - Edición de perfiles en tiempo real
/gestionar-lote              - Gestión completa de lotes apícolas
/botanical-chart/<comuna>    - Visualización botánica interactiva

[🔍 API RESTFUL - ACCESO PROGRAMÁTICO]
GET    /api/search            - Búsqueda general con autocompletado
GET    /api/autocomplete      - Sugerencias de búsqueda
GET    /api/table/<table>     - Datos de tabla específica
POST   /api/editar-usuario    - Actualización de datos de usuario
GET    /api/botanical-classes/<comuna> - Clases botánicas por comuna

[🔐 SISTEMA DE AUTENTICACIÓN]
/auth/login                  - Inicio de sesión con Google OAuth
/auth/callback               - Callback de autenticación
/auth/logout                 - Cierre de sesión seguro

[📊 TABLAS DE BASE DE DATOS]
- usuarios (perfiles de usuario)
- info_contacto (datos de contacto)
- ubicaciones (geolocalización)
- produccion_apicola (datos de producción)
- origenes_botanicos (clases botánicas)
- solicitudes_apicultor (gestión de solicitudes)

[⚙️ CONFIGURACIÓN ACTUAL]
- Puerto: {PORT}
- Debug: {DEBUG}
- Framework: Flask con arquitectura modular
- Autenticación: Supabase Auth + Google OAuth
- Responsive: Mobile-first con Tailwind CSS
- QR Codes: Generación dinámica con segno
- Despliegue: Vercel-ready con configuración optimizada

[🔧 VARIABLES DE ENTORNO]
- SUPABASE_URL, SUPABASE_KEY
- GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
- SECRET_KEY (Flask sessions)
- FLASK_ENV, FLASK_DEBUG (opcional)

🚀 **SERVIDOR INICIADO EXITOSAMENTE**
Accede a: {base_url}

📱 **Características destacadas:**
- ✅ Interfaz responsive mobile-first
- ✅ Búsqueda inteligente con autocompletado
- ✅ Perfiles públicos con QR codes
- ✅ Sistema de clasificación botánica visual
- ✅ Edición de perfiles en tiempo real
- ✅ Gestión completa de lotes apícolas
- ✅ API RESTful completa
- ✅ Autenticación segura con Google OAuth
"""
    print(welcome_msg)

def test_database_connection():
    """
    Función centralizada para probar la conexión con Supabase.
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Intentar una consulta simple para verificar la conexión
        response = db.client.table('usuarios').select('auth_user_id').limit(1).execute()
        if response.data is not None:
            return True, "Conexión exitosa con Supabase"
        else:
            return False, "No se pudieron obtener datos de Supabase"
    except Exception as e:
        return False, f"Error de conexión: {str(e)}"

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
        success, message = test_database_connection()
        if success:
            print("\n[✅] Conexión con Supabase establecida correctamente")
        else:
            print(f"\n[❌] Error de conexión: {message}")
        
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

# Pruebas para produccion 108