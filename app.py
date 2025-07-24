import logging
from flask import Flask, render_template, request, jsonify, url_for, redirect, send_file
from datetime import datetime
import io
import os
from dotenv import load_dotenv
from data_tables_supabase import list_tables, get_table_data
from supabase_client import db
from buscador import NavegadorSupabase
from qr_code.generator import QRGenerator
import segno
from io import BytesIO
import base64

# Load environment variables
load_dotenv()

# Desactivar logs de hpack y httpcore
logging.getLogger('hpack').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

# Configuración de logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Inicialización de la aplicación
app = Flask(__name__)

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

app.secret_key = 'tu_clave_secreta_aqui'  # Necesario para mensajes flash

# Configuración
DEBUG = False  # Siempre False para producción
PORT = int(os.environ.get('PORT', 3000))

# Configuración para producción
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False
app.json.sort_keys = False

# ====================
# Endpoints de la API
# ====================

@app.route('/api/test', methods=['GET'])
def test_connection_endpoint():
    """
    Prueba la conexión con la base de datos Supabase.
    
    GET /api/test
    """
    try:
        success, message = test_supabase_connection()
        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/table/<table_name>', methods=['GET'])
def get_table_data_endpoint(table_name):
    """
    Obtiene datos de una tabla específica con paginación.
    
    GET /api/table/<table_name>?page=1&per_page=20
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        success, result = get_table_data(table_name, page, per_page)
        
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

@app.route('/api/tables', methods=['GET'])
def list_tables_endpoint():
    """
    Lista todas las tablas disponibles en la base de datos.
    
    GET /api/tables
    """
    try:
        success, result = list_tables()
        if success:
            return jsonify({"success": True, "tables": result})
        else:
            return jsonify({"success": False, "error": result}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ====================
# Rutas de la interfaz web
# ====================

# Inicializar el navegador de Supabase
navegador = NavegadorSupabase(db.client)

@app.route('/', methods=['GET', 'POST'])
@app.route('/buscar', methods=['GET', 'POST'])
def buscar():
    """
    Maneja las rutas / y /buscar para buscar y mostrar información de usuarios.
    
    Métodos:
    - GET: Muestra el formulario de búsqueda o los resultados si se proporciona un usuario_id
    - POST: Realiza la búsqueda por ID de usuario
    """
    # Obtener el ID del usuario de los parámetros GET o del formulario POST
    user_id = request.args.get('usuario_id', '').strip()
    if request.method == 'POST':
        user_id = request.form.get('usuario_id', '').strip()
    
    # Si el ID es un segmento corto (8 caracteres), buscar el usuario completo
    if user_id and len(user_id) == 8 and '-' not in user_id:
        matching_users = []
        try:
            # Buscar usuarios cuyo ID comience con el segmento
            response = db.client.table('usuarios').select('id').execute()
            matching_users = [user for user in response.data 
                            if user.get('id', '').lower().startswith(user_id.lower())]
            
            if matching_users:
                # Redirigir a la versión con el ID completo
                return redirect(url_for('buscar', usuario_id=matching_users[0]['id']))
                
        except Exception as e:
            logger.error(f"Error al buscar usuario por segmento {user_id}: {str(e)}", exc_info=True)
    
    # Si se proporcionó un ID de usuario (completo), realizar la búsqueda
    if user_id and '-' in user_id:  # Verificar si es un UUID completo
        user, contact, locations, producciones, origenes_botanicos, solicitudes, error_msg = navegador.get_user_data(user_id)
        
        if error_msg:
            return render_template('buscar.html', error=error_msg)
            
        # Generar URL compartible
        uuid_segment = navegador.get_uuid_segment(user_id)
        shareable_url = url_for('get_usuario_by_uuid_segment', 
                              uuid_segment=uuid_segment, 
                              _external=True) if uuid_segment else ''
        
        # Preparar datos para la plantilla
        context = {
            'usuario': user,
            'contacto': contact,
            'ubicaciones': locations,
            'producciones': producciones,
            'origenes_botanicos': origenes_botanicos,
            'solicitudes': solicitudes,
            'usuario_id': user_id,
            'uuid_segment': uuid_segment,
            'shareable_url': shareable_url,
            'mostrar_resultados': True,
            'tiene_ubicaciones': bool(locations),
            'tiene_producciones': bool(producciones),
            'tiene_origenes_botanicos': bool(origenes_botanicos),
            'tiene_solicitudes': bool(solicitudes)
        }
        
        return render_template('buscar.html', **context)
    
    # Si es GET, mostrar el formulario de búsqueda
    return render_template('buscar.html')

@app.route('/sugerir', methods=['GET'])
def sugerir():
    """
    Endpoint para obtener sugerencias de autocompletado de usuarios.
    
    GET /sugerir?q=<término>
    
    Parámetros:
    - q: Término de búsqueda
    
    Retorna:
    - Lista de usuarios que coinciden con el término de búsqueda
    """
    try:
        termino = request.args.get('q', '').strip()
        if not termino:
            return jsonify({'results': []})
            
        # Obtener sugerencias de usuarios que coincidan con el término de búsqueda
        response = db.client.table('usuarios') \
            .select('id, username, tipo_usuario, status') \
            .ilike('username', f'%{termino}%') \
            .limit(10) \
            .execute()
            
        users = response.data if hasattr(response, 'data') else []
        
        # Formatear resultados para Select2
        results = [{
            'id': user['id'],
            'text': f"{user.get('username', '')} ({user.get('tipo_usuario', 'user')})"
        } for user in users]
        
        return jsonify({
            'results': results,
            'pagination': {'more': False}
        })
        
    except Exception as e:
        logger.error(f"Error en /sugerir: {str(e)}", exc_info=True)
        return jsonify({"error": "Error al obtener sugerencias"}), 500

@app.route('/api/test-db', methods=['GET'])
def test_db():
    """
    Prueba la conexión con la base de datos y devuelve información del sistema.
    
    GET /api/test-db
    """
    try:
        # Verificar conexión a Supabase
        response = db.client.table('usuarios').select('count', count='exact').execute()
        return jsonify({
            "conexion": "OK",
            "total_usuarios": response.count if hasattr(response, 'count') else 'N/A',
            "version": "1.0.0"
        })
    except Exception as e:
        logger.error(f"Error en /api/test-db: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/usuario/<uuid_segment>')
def get_usuario_by_uuid_segment(uuid_segment):
    """
    Redirige al perfil del usuario usando el primer segmento de su UUID.
    
    GET /api/usuario/550e8400 -> redirige al perfil del usuario con ID que comience con 550e8400
    """
    try:
        if not uuid_segment or len(uuid_segment) != 8:
            return jsonify({"error": "Formato de segmento UUID inválido. Debe tener 8 caracteres."}), 400
            
        # Convertir a minúsculas para consistencia
        uuid_segment = uuid_segment.lower()
        
        # Obtener todos los usuarios y filtrar localmente
        response = db.client.table('usuarios').select('id').execute()
        
        # Buscar usuario cuyo ID comience con el segmento proporcionado ......... MODIFICAR PARA QUE SEA DIRECTO CON SUPABASE
        matching_users = [user for user in response.data 
                         if user.get('id', '').lower().startswith(uuid_segment)]
        
        if not matching_users:
            return jsonify({"error": f"No se encontró ningún usuario con el ID que comience con {uuid_segment}"}), 404
            
        # Tomar el primer usuario que coincida
        user_id = matching_users[0]['id']
        
        # Redirigir a la página de búsqueda con el ID completo
        return redirect(url_for('buscar', usuario_id=user_id))
        
    except Exception as e:
        logger.error(f"Error al buscar usuario por segmento UUID {uuid_segment}: {str(e)}", exc_info=True)
        return jsonify({"error": "Error interno del servidor"}), 500

@app.route('/api/usuario/<uuid_segment>/qr')
def get_user_qr(uuid_segment):
    """
    Genera y devuelve un código QR que redirecciona al perfil del usuario.
    
    GET /api/usuario/550e8400/qr?format=png -> Devuelve una imagen PNG del QR
    GET /api/usuario/550e8400/qr?format=svg -> Devuelve una imagen SVG del QR
    GET /api/usuario/550e8400/qr?format=json -> Devuelve un JSON con el QR en base64
    """
    try:
        # Validar formato de UUID
        if not uuid_segment or len(uuid_segment) != 8:
            return jsonify({"error": "Formato de segmento UUID inválido. Debe tener 8 caracteres."}), 400
            
        # Convertir a minúsculas para consistencia
        uuid_segment = uuid_segment.lower()
        
        # Reutilizar la lógica existente para buscar el usuario por UUID segment
        # Buscar usuario cuyo ID comience con el segmento proporcionado
        response = db.client.table('usuarios').select('id').execute()
        
        matching_users = [user for user in response.data 
                        if user.get('id', '').lower().startswith(uuid_segment)]
        
        if not matching_users:
            return jsonify({"error": f"No se encontró ningún usuario con el ID que comience con {uuid_segment}"}), 404
            
        # Obtener el ID completo del usuario
        user_id = matching_users[0]['id']
        
        # Obtener formato solicitado (solo permitimos png y json)
        qr_format = request.args.get('format', 'png')
        scale = int(request.args.get('scale', 5))
        
        # Crear generador QR
        qr_generator = QRGenerator()
        
        # Generar la URL web para el QR (apuntando a la página de búsqueda con el UUID completo)
        base_url = request.url_root.rstrip('/')
        profile_url = f"{base_url}/buscar?usuario_id={user_id}"
        
        # Generar QR directamente con segno
        qr = segno.make(profile_url, error='m')
        
        if qr_format == 'png':
            # Generar QR en PNG y devolverlo como archivo
            qr_png = qr.png_bytes(scale=scale)
            if qr_png:
                return send_file(io.BytesIO(qr_png), mimetype='image/png')
            else:
                return jsonify({"error": "Error al generar QR"}), 500
                
        elif qr_format == 'json':
            # Generar QR en formato JSON con imagen base64
            output = BytesIO()
            qr.save(output, kind='png', scale=scale)
            qr_base64 = base64.b64encode(output.getvalue()).decode('ascii')
            
            if qr_base64:
                return jsonify({
                    "success": True,
                    "qr_code": f"data:image/png;base64,{qr_base64}",
                    "user_id": user_id,
                    "uuid_segment": uuid_segment
                })
            else:
                return jsonify({"error": "Error al generar QR"}), 500
        else:
            return jsonify({"error": f"Formato '{qr_format}' no soportado. Formatos válidos: png, json"}), 400
            
    except Exception as e:
        logger.error(f"Error al generar QR para usuario con segmento UUID {uuid_segment}: {str(e)}", exc_info=True)
        return jsonify({"error": "Error interno del servidor"}), 500

# ====================
# Punto de entrada
# ====================

def list_routes():
    """
    Muestra todas las rutas registradas en la aplicación con sus métodos HTTP.
    Agrupadas por categorías para mejor legibilidad.
    """
    # Agrupar rutas por categoría
    api_routes = []
    web_routes = []
    static_routes = []
    
    for rule in app.url_map.iter_rules():
        methods = sorted([m for m in rule.methods if m not in ('OPTIONS', 'HEAD')])
        route_path = str(rule)
        route_info = {
            'endpoint': rule.endpoint,
            'path': route_path,
            'methods': methods
        }
        
        if rule.endpoint == 'static':
            static_routes.append(route_info)
        elif route_path.startswith('/api/'):
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
    
    # 3. Rutas estáticas (opcional, si quieres mostrarlas)
    if static_routes:
        output.append("\n=== RUTAS ESTÁTICAS ===")
        for route in static_routes:
            output.append(f"{route['path']:50} [GET      ]")
    
    return '\n'.join(output)

def print_welcome_message():
    """Muestra un mensaje de bienvenida con información de los endpoints principales."""
    welcome_msg = """
=== MELI SUPABASE TEST ===

ENDPOINTS PRINCIPALES:

[WEB]
/                       - Página principal del buscador
/buscar                 - Buscar usuarios (GET: formulario, POST: resultados)
/sugerir?q=<termino>   - Autocompletado de usuarios

[API]
/api/usuario/<uuid>     - Obtener usuario por segmento de UUID (8 caracteres)
/api/test               - Probar conexión con Supabase
/api/tables             - Listar todas las tablas
/api/table/<tabla>      - Ver datos de una tabla específica
/api/test-db            - Verificar estado de la base de datos

[EJEMPLOS]
http://localhost:3000/api/table/usuarios?page=1&per_page=10
http://localhost:3000/api/usuario/ce27e79e
http://localhost:3000/sugerir?q=nombre
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
        db.test_connection()
        print("\n[OK] Conexión con Supabase establecida correctamente")
        
        # Mostrar rutas detalladas
        print("\n=== RUTAS REGISTRADAS ===")
        print(list_routes())
        
        # Mostrar mensaje de bienvenida
        print_welcome_message()
        
        # Iniciar la aplicación
        print(f"\n🚀 Iniciando servidor en http://127.0.0.1:{PORT}/buscar")
        print("Presiona CTRL+C para salir\n")
        
        # Iniciar la aplicación sin reloader
        app.run(debug=DEBUG, port=PORT, use_reloader=False)
    except Exception as e:
        print(f"\n[ERROR] Error al conectar con Supabase: {str(e)}")
        print("Asegúrate de que las credenciales en el archivo .env sean correctas.")

# Para Vercel, exponemos la app directamente
if __name__ == '__main__':
    main()
