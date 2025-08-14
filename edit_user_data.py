"""
Módulo de endpoints para edición modular de datos de usuario.
Permite editar datos personales en las tablas usuarios, info_contacto y ubicaciones
de forma separada, usando el UUID del usuario como referencia absoluta.
"""

from flask import Blueprint, request, jsonify, session, g
from functools import wraps
from supabase_client import db
from supabase import create_client
import logging
import re
import os
import traceback

logger = logging.getLogger(__name__)

# Crear blueprint para endpoints de edición
edit_bp = Blueprint('edit', __name__)

def get_authenticated_supabase_client():
    """Crea un cliente de Supabase autenticado con el token del usuario actual."""
    try:
        # Obtener el token JWT del usuario desde la sesión
        access_token = session.get('access_token')
        refresh_token = session.get('refresh_token')
        
        # Crear cliente con credenciales de Supabase
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")  # Anon key, no service role
        
        if not supabase_url or not supabase_key:
            return None, "Credenciales de Supabase no configuradas"
        
        client = create_client(supabase_url, supabase_key)
        
        # Si tenemos tokens JWT, usarlos para autenticación RLS
        if access_token:
            try:
                # Establecer la sesión en el cliente para RLS
                client.auth.set_session(access_token, refresh_token or '')
                logger.info("Cliente autenticado con JWT para RLS")
                return client, None
            except Exception as session_error:
                logger.error(f"Error al establecer sesión JWT: {str(session_error)}")
                # Continuar con fallback
        
        # Fallback: usar cliente sin JWT (puede requerir políticas RLS menos restrictivas)
        logger.warning("Usando cliente sin JWT - verificar políticas RLS")
        return client, None
        
    except Exception as e:
        logger.error(f"Error general en cliente autenticado: {str(e)}")
        return None, f"Error al crear cliente autenticado: {str(e)}"

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

@edit_bp.route('/api/edit/usuarios', methods=['POST'])
@login_required_api
def edit_usuarios():
    """
    Edita datos del usuario autenticado en la tabla usuarios.
    Solo permite editar username y role. tipo_usuario siempre es "Regular".
    
    POST /api/edit/usuarios
    Body JSON: {username, role}
    """
    try:
        user_uuid = g.user.get('user_uuid')
        if not user_uuid:
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Datos requeridos"}), 400
        
        # Solo permitir username y role
        update_data = {'tipo_usuario': 'Regular'}  # Forzar siempre Regular
        
        # Validar username
        if 'username' in data:
            username = data['username']
            is_valid, error = validate_username(username)
            if not is_valid:
                return jsonify({"success": False, "error": error}), 400
            update_data['username'] = username
        
        # Validar role con opciones fijas
        if 'role' in data:
            role = data['role']
            allowed_roles = ['APICULTOR', 'PROVEEDOR', 'PRESTADOR DE SERVICIOS']
            if role not in allowed_roles:
                return jsonify({"success": False, "error": f"Rol debe ser uno de: {', '.join(allowed_roles)}"}), 400
            update_data['role'] = role
        
        if not update_data or len(update_data) <= 1:  # Solo tiene tipo_usuario
            return jsonify({"success": False, "error": "No hay campos válidos para actualizar"}), 400
        
        # Obtener cliente autenticado
        auth_client, error = get_authenticated_supabase_client()
        if error:
            logger.error(f"Error de autenticación: {error}")
            return jsonify({"success": False, "error": "Error de autenticación"}), 401
        
        # Actualizar datos con cliente autenticado
        logger.info(f"Actualizando usuario {user_uuid} con datos: {update_data}")
        
        try:
            # Verificar si el usuario existe primero
            check_result = auth_client.table('usuarios')\
                .select('id')\
                .eq('id', user_uuid)\
                .execute()
            
            if not check_result.data:
                logger.error(f"Usuario con ID {user_uuid} no encontrado en la tabla usuarios")
                return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
            
            # Realizar la actualización
            result = auth_client.table('usuarios')\
                .update(update_data)\
                .eq('id', user_uuid)\
                .execute()
            
            logger.info(f"Respuesta de actualización: {result}")
            logger.info(f"Datos actualizados: {result.data}")
            logger.info(f"Conteo de datos: {len(result.data) if result.data else 0}")
            
            # Verificar si la actualización fue exitosa por el conteo de filas afectadas
            if hasattr(result, 'count') and result.count is not None:
                logger.info(f"Filas afectadas: {result.count}")
            
            # Siempre que no haya error, consideramos la actualización exitosa
            if result.data and len(result.data) > 0:
                return jsonify({
                    "success": True,
                    "message": "Datos de usuario actualizados correctamente",
                    "data": result.data[0],
                    "rows_affected": len(result.data)
                })
            else:
                # Verificar si hay algún mensaje de error
                if hasattr(result, 'error') and result.error:
                    logger.error(f"Error en actualización: {result.error}")
                    return jsonify({"success": False, "error": str(result.error)}), 500
                else:
                    # La actualización fue exitosa pero Supabase no retorna datos
                    # Verificar que los datos realmente se actualizaron
                    verification = auth_client.table('usuarios')\
                        .select('*')\
                        .eq('id', user_uuid)\
                        .single()\
                        .execute()
                    
                    if verification.data:
                        logger.info(f"Verificación exitosa: {verification.data}")
                        return jsonify({
                            "success": True, 
                            "message": "Datos actualizados exitosamente",
                            "data": verification.data,
                            "verified": True
                        })
                    else:
                        logger.warning(f"No se pudieron verificar los datos actualizados")
                        return jsonify({
                            "success": True, 
                            "message": "Datos actualizados exitosamente pero no verificados",
                            "data": {"id": user_uuid, **update_data},
                            "verified": False
                        })
                
        except Exception as db_error:
            logger.error(f"Error en la consulta a la base de datos: {str(db_error)}")
            logger.error(f"Tipo de error: {type(db_error)}")
            return jsonify({"success": False, "error": f"Error en la base de datos: {str(db_error)}"}), 500
            
    except Exception as e:
        logger.error(f"Error al editar usuarios: {str(e)}")
        logger.error(f"Tipo de error: {type(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@edit_bp.route('/api/edit/ubicaciones', methods=['POST'])
@login_required_api
def edit_ubicaciones():
    """
    Endpoint simplificado para agregar una nueva ubicación del usuario.
    Solo permite formato PLUS CODE o latitud/longitud literal.
    Reemplaza la ubicación anterior del usuario.
    
    POST /api/edit/ubicaciones
    Body JSON: {ubicacion}
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Datos requeridos"}), 400
        
        # Solo aceptar formato PLUS CODE o lat/long
        ubicacion_input = data.get('ubicacion', '').strip()
        if not ubicacion_input:
            return jsonify({"success": False, "error": "Ubicación requerida"}), 400
        
        # Solo aceptar formato PLUS CODE de Google Maps
        if '+' not in ubicacion_input or len(ubicacion_input.split('+')) != 2:
            return jsonify({"success": False, "error": "Formato inválido. Solo se acepta PLUS CODE de Google Maps (ej: CVV6+HJ7 Pichipehuenco, Lonquimay)"}), 400
        
        # Validar que tenga el formato básico de PLUS CODE
        parts = ubicacion_input.split('+')
        if len(parts[0]) < 4 or len(parts[1].split()[0]) < 2:
            return jsonify({"success": False, "error": "PLUS CODE inválido. Use el formato de Google Maps (ej: CVV6+HJ7 Pichipehuenco)"}), 400
        
        ubicacion_data = {
            'nombre': ubicacion_input,
            'direccion': ubicacion_input,
            'latitud': None,
            'longitud': None,
            'tipo_ubicacion': 'PLUS_CODE',
            'descripcion': f'Ubicación PLUS CODE: {ubicacion_input}'
        }
        
        # Agregar UUID del usuario
        user_uuid = g.user.get('user_uuid')
        if not user_uuid:
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
            
        ubicacion_data['usuario_id'] = user_uuid
        
        # Obtener cliente autenticado
        auth_client, error = get_authenticated_supabase_client()
        if error:
            logger.error(f"Error de autenticación: {error}")
            return jsonify({"success": False, "error": "Error de autenticación"}), 401
        
        # Reemplazar ubicación existente: eliminar y crear nueva
        auth_client.table('ubicaciones').delete().eq('usuario_id', user_uuid).execute()
        result = auth_client.table('ubicaciones').insert(ubicacion_data).execute()
        
        if result.data:
            return jsonify({"success": True, "message": "Ubicación actualizada exitosamente"})
        else:
            return jsonify({"success": False, "error": "Error al actualizar ubicación"}), 500
            
    except Exception as e:
        logger.error(f"Error en edit_ubicaciones: {str(e)}")
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
        
        # Obtener cliente autenticado
        auth_client, error = get_authenticated_supabase_client()
        if error:
            logger.error(f"Error de autenticación: {error}")
            return jsonify({"success": False, "error": "Error de autenticación"}), 401
        
        # Verificar si existe registro
        existing = auth_client.table('info_contacto')\
            .select('id')\
            .eq('usuario_id', user_uuid)\
            .execute()
        
        if existing.data:
            # Obtener cliente autenticado
            auth_client, error = get_authenticated_supabase_client()
            if error:
                logger.error(f"Error de autenticación: {error}")
                return jsonify({"success": False, "error": "Error de autenticación"}), 401
            
            # Actualizar ubicación con cliente autenticado
            result = auth_client.table('ubicaciones')\
                .update({"ubicacion": ubicacion})\
                .eq('usuario_id', user_uuid)\
                .execute()
        else:
            # Crear nuevo
            update_data['usuario_id'] = user_uuid
            result = auth_client.table('info_contacto')\
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

@edit_bp.route('/api/debug/session', methods=['GET'])
@login_required_api
def debug_session():
    """Endpoint de depuración para verificar tokens JWT en la sesión."""
    try:
        return jsonify({
            "success": True,
            "session_data": {
                "user_id": session.get('user_id'),
                "access_token": session.get('access_token')[:20] + "..." if session.get('access_token') else None,
                "refresh_token": session.get('refresh_token')[:20] + "..." if session.get('refresh_token') else None,
                "has_access_token": bool(session.get('access_token')),
                "has_refresh_token": bool(session.get('refresh_token'))
            }
        })
    except Exception as e:
        logger.error(f"Error en debug_session: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

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
        
        # Obtener cliente autenticado
        auth_client, error = get_authenticated_supabase_client()
        if error:
            logger.error(f"Error de autenticación: {error}")
            return jsonify({"success": False, "error": "Error de autenticación"}), 401
        
        if table_name == 'usuarios':
            result = auth_client.table('usuarios')\
                .select('*')\
                .eq('id', user_uuid)\
                .single()\
                .execute()
        elif table_name == 'info_contacto':
            result = auth_client.table('info_contacto')\
                .select('*')\
                .eq('usuario_id', user_uuid)\
                .single()\
                .execute()
            if not result.data:
                # No existe, crear nueva ubicación
                result = auth_client.table('ubicaciones')\
                    .insert({"usuario_id": user_uuid, "ubicacion": ubicacion})\
                    .execute()
        elif table_name == 'ubicaciones':
            result = auth_client.table('ubicaciones')\
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
