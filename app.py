import logging
from flask import Flask
from datetime import datetime
import os
from dotenv import load_dotenv

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
    PERMANENT_SESSION_LIFETIME=3600 * 24 * 7,  # 7 días
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

# Registrar blueprints
app.register_blueprint(api_bp)
app.register_blueprint(web_bp)

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

def print_welcome_message():
    """Muestra un mensaje de bienvenida completo con información de todos los endpoints."""
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
/register                    - Formulario de registro de usuarios
/logout                      - Cierre de sesión
/profile/<user_id>           - Perfil de usuario (acepta UUID completo o segmento)
/buscar                      - Búsqueda de usuarios
/gestionar-lote              - Gestión de lotes de miel (requiere login)
/auth/callback               - Callback de autenticación OAuth

[🔌 RUTAS API - SERVICIOS REST]
"""
    api_routes = [
        ('/api/test', 'GET', 'Prueba de conexión con Supabase'),
        ('/api/tables', 'GET', 'Lista todas las tablas disponibles'),
        ('/api/table/<tabla>', 'GET', 'Datos paginados de cualquier tabla'),
        ('/api/gestionar-lote', 'POST', 'Crear/actualizar lotes de miel'),
        ('/api/test-db', 'GET', 'Estado detallado de la base de datos'),
        ('/api/usuario/<segment>', 'GET', 'Redirige al perfil usando segmento UUID (8 chars)'),
        ('/api/auth/login', 'POST', 'Login API (devuelve JSON)'),
        ('/api/auth/register', 'POST', 'Registro API (devuelve JSON)'),
        ('/api/auth/session', 'GET', 'Verificar estado de sesión'),
        ('/api/auth/logout', 'POST', 'Cerrar sesión API'),
    ]
    
    welcome_msg += "\n[🔌 RUTAS API - SERVICIOS REST]\n"
    for route, method, description in api_routes:
        welcome_msg += f"- `{method} {route}` - {description}\n"
    
    welcome_msg += f"""
[📋 TABLAS DISPONIBLES EN API]
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

[📱 EJEMPLOS DE USO]
# Buscar usuario por segmento UUID:
curl http://localhost:{PORT}/api/usuario/550e8400

# Obtener tabla de usuarios:
curl http://localhost:{PORT}/api/table/usuarios?page=1&per_page=10

# Probar conexión:
curl http://localhost:{PORT}/api/test

# Acceder al perfil:
http://localhost:{PORT}/profile/550e8400-e29b-41d4-a716-446655440000

[⚙️ CONFIGURACIÓN]
- Puerto: {PORT}
- Debug: {DEBUG}
- Base de datos: Supabase PostgreSQL
- Framework: Flask con Blueprints
- Autenticación: Supabase Auth

🚀 **SERVIDOR INICIADO**
Accede a: http://127.0.0.1:{PORT}/
"""
    print(welcome_msg)

def main():
    """Función principal que inicia la aplicación."""
    try:
        # Configurar la codificación de la consola para Windows (solo local)
        import sys
        import io
        
        # Configurar la salida estándar
        if sys.stdout.encoding != 'utf-8':
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        
        # Verificar la conexión con Supabase al inicio
        from supabase_client import db
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
        
        # Iniciar la aplicación sin reloader
        app.run(host='0.0.0.0', port=PORT, debug=DEBUG, use_reloader=False)
        
    except Exception as e:
        print(f"\n[❌] Error al iniciar la aplicación: {str(e)}")
        print("Asegúrate de que las credenciales en el archivo .env sean correctas.")

# Para Vercel, exponemos la app directamente
if __name__ == '__main__':
    main()
