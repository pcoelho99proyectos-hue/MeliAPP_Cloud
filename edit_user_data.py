"""
Módulo de endpoints para edición modular de datos de usuario.
Permite editar datos personales en las tablas usuarios, info_contacto y ubicaciones
de forma separada, usando el UUID del usuario como referencia absoluta.
"""

from flask import Blueprint, request, jsonify, session, g
from functools import wraps
from supabase_client import db
import logging
import re

logger = logging.getLogger(__name__)

# Crear blueprint para endpoints de edición
edit_bp = Blueprint('edit', __name__)

def login_required_api(f):
    """Decorador para requerir autenticación en endpoints API."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not g.user or not g.user.get('user_uuid'):
            return jsonify({"success": False, "error": "Autenticación requerida"}), 401
        return f(*args, **kwargs)
    return decorated_function

def validate_username(username):
    """Valida formato y disponibilidad del username."""
    if not username or len(username) < 3 or len(username) > 80:
        return False, "Username debe tener entre 3 y 80 caracteres"
    
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return False, "Username solo puede contener letras, números, guiones y underscores"
    
    # Verificar disponibilidad
    try:
        response = db.client.table('usuarios')\
            .select('id')\
            .eq('username', username)\
            .execute()
        
        if response.data:
            return False, "Username ya está en uso"
    except Exception as e:
        return False, f"Error al verificar username: {str(e)}"
    
    return True, None

def validate_email(email):
    """Valida formato de email."""
    if not email:
        return True, None
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, "Formato de email inválido"
    
    return True, None

def validate_coordinates(lat, lng):
    """Valida coordenadas geográficas."""
    try:
        lat = float(lat)
        lng = float(lng)
        
        if not (-90 <= lat <= 90):
            return False, "Latitud debe estar entre -90 y 90 grados"
        
        if not (-180 <= lng <= 180):
            return False, "Longitud debe estar entre -180 y 180 grados"
        
        return True, None
    except (ValueError, TypeError):
        return False, "Coordenadas deben ser números válidos"

@edit_bp.route('/api/edit/usuarios', methods=['POST'])
@login_required_api
def edit_usuarios():
    """
    Edita datos del usuario autenticado en la tabla usuarios.
    Solo permite editar campos específicos del usuario actual.
    
    POST /api/edit/usuarios
    Body JSON: {username, tipo_usuario, role}
    """
    try:
        user_uuid = g.user.get('user_uuid')
        if not user_uuid:
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Datos requeridos"}), 400
        
        # Campos permitidos para edición
        allowed_fields = ['username', 'tipo_usuario', 'role']
        update_data = {}
        
        # Validar y filtrar campos
        for field in allowed_fields:
            if field in data:
                value = data[field]
                
                if field == 'username':
                    is_valid, error = validate_username(value)
                    if not is_valid:
                        return jsonify({"success": False, "error": error}), 400
                    update_data[field] = value
                
                elif field == 'tipo_usuario':
                    if value not in ['Regular', 'Admin']:
                        return jsonify({"success": False, "error": "tipo_usuario inválido. Use 'Regular' o 'Admin'"}), 400
                    update_data[field] = value
                
                elif field == 'role':
                    if value not in ['regular', 'apicultor', 'productor', 'comercializador']:
                        return jsonify({"success": False, "error": "role inválido"}), 400
                    update_data[field] = value
        
        if not update_data:
            return jsonify({"success": False, "error": "No hay campos válidos para actualizar"}), 400
        
        # Actualizar datos
        result = db.client.table('usuarios')\
            .update(update_data)\
            .eq('id', user_uuid)\
            .execute()
        
        if result.data:
            return jsonify({
                "success": True,
                "message": "Datos de usuario actualizados correctamente",
                "data": result.data[0]
            })
        else:
            return jsonify({"success": False, "error": "No se pudieron actualizar los datos"}), 500
            
    except Exception as e:
        logger.error(f"Error al editar usuarios: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@edit_bp.route('/api/edit/info_contacto', methods=['POST'])
@login_required_api
def edit_info_contacto():
    """
    Edita o crea información de contacto del usuario autenticado.
    
    POST /api/edit/info_contacto
    Body JSON: {nombre_completo, nombre_empresa, correo_principal, telefono_principal, direccion, comuna, region}
    """
    try:
        user_uuid = g.user.get('user_uuid')
        if not user_uuid:
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Datos requeridos"}), 400
        
        # Validar campos requeridos
        if 'nombre_completo' in data:
            if not data['nombre_completo'] or len(data['nombre_completo']) < 2 or len(data['nombre_completo']) > 150:
                return jsonify({"success": False, "error": "nombre_completo debe tener entre 2 y 150 caracteres"}), 400
        
        if 'correo_principal' in data and data['correo_principal']:
            is_valid, error = validate_email(data['correo_principal'])
            if not is_valid:
                return jsonify({"success": False, "error": error}), 400
        
        # Preparar datos para actualización
        allowed_fields = [
            'nombre_completo', 'nombre_empresa', 'correo_principal',
            'telefono_principal', 'direccion', 'comuna', 'region'
        ]
        update_data = {k: v for k, v in data.items() if k in allowed_fields}
        
        if not update_data:
            return jsonify({"success": False, "error": "No hay campos válidos para actualizar"}), 400
        
        # Verificar si existe registro
        existing = db.client.table('info_contacto')\
            .select('id')\
            .eq('usuario_id', user_uuid)\
            .execute()
        
        if existing.data:
            # Actualizar
            result = db.client.table('info_contacto')\
                .update(update_data)\
                .eq('usuario_id', user_uuid)\
                .execute()
        else:
            # Crear nuevo
            update_data['usuario_id'] = user_uuid
            result = db.client.table('info_contacto')\
                .insert(update_data)\
                .execute()
        
        if result.data:
            return jsonify({
                "success": True,
                "message": "Información de contacto actualizada correctamente",
                "data": result.data[0]
            })
        else:
            return jsonify({"success": False, "error": "No se pudieron actualizar los datos"}), 500
            
    except Exception as e:
        logger.error(f"Error al editar info_contacto: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@edit_bp.route('/api/edit/ubicaciones', methods=['POST'])
@login_required_api
def edit_ubicaciones():
    """
    Edita o crea ubicaciones del usuario autenticado.
    
    POST /api/edit/ubicaciones
    Body JSON: {nombre, latitud, longitud, descripcion}
    """
    try:
        user_uuid = g.user.get('user_uuid')
        if not user_uuid:
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Datos requeridos"}), 400
        
        # Validar campos requeridos
        if 'nombre' not in data or not data['nombre']:
            return jsonify({"success": False, "error": "nombre es requerido"}), 400
        
        if len(data['nombre']) < 2 or len(data['nombre']) > 100:
            return jsonify({"success": False, "error": "nombre debe tener entre 2 y 100 caracteres"}), 400
        
        if 'latitud' in data and 'longitud' in data:
            is_valid, error = validate_coordinates(data['latitud'], data['longitud'])
            if not is_valid:
                return jsonify({"success": False, "error": error}), 400
        
        # Preparar datos
        allowed_fields = ['nombre', 'latitud', 'longitud', 'descripcion', 'norma_geo']
        update_data = {k: v for k, v in data.items() if k in allowed_fields}
        
        # Si viene ID, es actualización; si no, es creación
        ubicacion_id = data.get('id')
        
        if ubicacion_id:
            # Actualizar ubicación existente
            result = db.client.table('ubicaciones')\
                .update(update_data)\
                .eq('id', ubicacion_id)\
                .eq('usuario_id', user_uuid)\
                .execute()
        else:
            # Crear nueva ubicación
            update_data['usuario_id'] = user_uuid
            result = db.client.table('ubicaciones')\
                .insert(update_data)\
                .execute()
        
        if result.data:
            return jsonify({
                "success": True,
                "message": "Ubicación actualizada correctamente",
                "data": result.data[0]
            })
        else:
            return jsonify({"success": False, "error": "No se pudieron actualizar los datos"}), 500
            
    except Exception as e:
        logger.error(f"Error al editar ubicaciones: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@edit_bp.route('/api/data/<table_name>', methods=['GET'])
@login_required_api
def get_user_data(table_name):
    """
    Obtiene los datos personales del usuario autenticado de una tabla específica.
    
    GET /api/data/<usuarios|info_contacto|ubicaciones>
    """
    try:
        user_uuid = g.user.get('user_uuid')
        if not user_uuid:
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
        
        allowed_tables = ['usuarios', 'info_contacto', 'ubicaciones']
        if table_name not in allowed_tables:
            return jsonify({"success": False, "error": "Tabla no permitida"}), 400
        
        if table_name == 'usuarios':
            result = db.client.table('usuarios')\
                .select('*')\
                .eq('id', user_uuid)\
                .single()\
                .execute()
        elif table_name == 'info_contacto':
            result = db.client.table('info_contacto')\
                .select('*')\
                .eq('usuario_id', user_uuid)\
                .single()\
                .execute()
        elif table_name == 'ubicaciones':
            result = db.client.table('ubicaciones')\
                .select('*')\
                .eq('usuario_id', user_uuid)\
                .execute()
        
        return jsonify({
            "success": True,
            "data": result.data or ({} if table_name != 'ubicaciones' else [])
        })
        
    except Exception as e:
        logger.error(f"Error al obtener datos de {table_name}: {str(e)}")
        return jsonify({"success": False, "error": "Error al obtener datos"}), 500
