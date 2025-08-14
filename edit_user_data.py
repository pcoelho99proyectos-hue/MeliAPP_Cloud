from flask import Blueprint, request, jsonify, g, session
import logging
from datetime import datetime
from supabase import create_client
import os

logger = logging.getLogger(__name__)

# Configurar Supabase
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')

edit_bp = Blueprint('edit_user_data', __name__)

def get_authenticated_client():
    """Obtener cliente Supabase autenticado con JWT del usuario"""
    try:
        # Debug: imprimir estado de la sesión
        logger.info(f"g.user: {g.user}")
        logger.info(f"session keys: {list(session.keys())}")
        
        # Intentar múltiples fuentes de token
        token = None
        
        # 1. Desde session
        if 'access_token' in session:
            token = session['access_token']
            logger.info("Token obtenido desde session")
        
        # 2. Desde g.user
        elif hasattr(g, 'user') and g.user:
            token = g.user.get('access_token')
            logger.info("Token obtenido desde g.user")
        
        # 3. Desde auth_manager si está disponible
        else:
            try:
                from auth_manager import AuthManager
                auth_manager = AuthManager()
                current_user = auth_manager.load_current_user()
                if current_user and 'access_token' in current_user:
                    token = current_user['access_token']
                    logger.info("Token obtenido desde auth_manager")
            except ImportError:
                pass
        
        if not token:
            logger.error("No se encontró token de acceso en ninguna fuente")
            logger.error(f"Session: {dict(session)}")
            logger.error(f"g.user: {getattr(g, 'user', 'No disponible')}")
            return None
            
        logger.info(f"Token encontrado: {token[:10]}...")
        
        # Crear cliente autenticado
        auth_client = create_client(supabase_url, supabase_key)
        
        # Configurar autenticación usando headers
        auth_client.postgrest.auth(token)
        
        # Verificar que el cliente esté autenticado
        try:
            # Probar con una consulta simple
            test_result = auth_client.table('usuarios').select('id').limit(1).execute()
            logger.info("Cliente autenticado exitosamente")
            return auth_client
        except Exception as e:
            logger.error(f"Error verificando autenticación: {e}")
            return None
            
    except Exception as e:
        logger.error(f"Error completo en get_authenticated_client: {e}")
        return None

@edit_bp.route('/api/edit/usuarios', methods=['POST'])
def edit_usuarios():
    """Editar información de usuario"""
    try:
        # Verificar autenticación
        auth_client = get_authenticated_client()
        if not auth_client:
            return jsonify({"success": False, "error": "Error de autenticación"}), 401
        
        user_uuid = g.user.get('user_uuid')
        if not user_uuid:
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Datos requeridos"}), 400
        
        # Actualizar campos sin validación restrictiva
        valid_fields = ['username', 'tipo_usuario', 'role']
        update_data = {}
        
        for field in valid_fields:
            if field in data and data[field] is not None:
                value = data[field]
                
                # Solo validar username si se proporciona
                if field == 'username' and value:
                    if len(value) < 2 or len(value) > 80:
                        return jsonify({"success": False, "error": "Username debe tener entre 2 y 80 caracteres"}), 400
                    update_data['username'] = value
                
                elif field == 'username' and not value:
                    update_data['username'] = value  # Permitir vacío
                
                elif field in ['tipo_usuario', 'role']:
                    update_data[field] = value  # Permitir cualquier valor incluyendo vacío
        
        if not update_data:
            return jsonify({"success": False, "error": "No hay campos para actualizar"}), 400
        
        # Obtener auth_user_id desde la tabla usuarios usando el user_uuid
        user_info = auth_client.table('usuarios').select('auth_user_id').eq('id', user_uuid).single().execute()
        if not user_info.data:
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
            
        auth_user_id = user_info.data['auth_user_id']
        logger.info(f"Usando auth_user_id: {auth_user_id}")
        
        # Verificar unicidad de username si se está actualizando
        if 'username' in update_data:
            logger.info(f"Verificando unicidad de username: {update_data['username']}")
            existing = auth_client.table('usuarios').select('id').eq('username', update_data['username']).neq('auth_user_id', auth_user_id).execute()
            logger.info(f"Resultado verificación username: {existing.data}")
            if existing.data:
                logger.error(f"Username duplicado encontrado: {existing.data}")
                return jsonify({"success": False, "error": "Username ya existe"}), 400
            logger.info("Username disponible")
        
        # Agregar timestamp para forzar actualización en cambios de case
        update_data['last_login'] = datetime.utcnow().isoformat()
        
        # Actualizar usuario usando auth_user_id para que coincida con RLS policy
        logger.info(f"Actualizando usuario {user_uuid} con datos: {update_data}")
        update_result = auth_client.table('usuarios').update(update_data).eq('auth_user_id', auth_user_id).execute()
        logger.info(f"Resultado actualización: {update_result}")
        
        if not update_result.data or len(update_result.data) == 0:
            logger.error("No se encontraron datos en la respuesta de actualización")
            return jsonify({"success": False, "error": "No se pudo actualizar el usuario"}), 500
        
        # Obtener datos actualizados
        logger.info("Obteniendo datos actualizados del usuario")
        user_data = auth_client.table('usuarios').select('*').eq('id', user_uuid).single().execute()
        logger.info(f"Datos obtenidos: {user_data.data}")
        
        return jsonify({
            "success": True,
            "message": "Usuario actualizado correctamente",
            "data": user_data.data,
            "profile_url": f"/profile/{user_uuid}"
        })
        
    except Exception as e:
        logger.error(f"Error completo editando usuario: {e}")
        logger.error(f"Tipo de error: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500

@edit_bp.route('/api/edit/ubicaciones', methods=['POST'])
def edit_ubicaciones():
    """Editar ubicaciones del usuario"""
    try:
        auth_client = get_authenticated_client()
        if not auth_client:
            return jsonify({"success": False, "error": "Error de autenticación"}), 401
        
        user_uuid = g.user.get('user_uuid')
        if not user_uuid:
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Datos requeridos"}), 400
        
        # Obtener usuario_id desde UUID
        usuario = auth_client.table('usuarios').select('id').eq('id', user_uuid).single().execute()
        if not usuario.data:
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
        
        # Actualizar ubicaciones
        update_data = {k: v for k, v in data.items() if k in ['direccion', 'ciudad', 'provincia', 'pais', 'codigo_postal']}
        
        if not update_data:
            return jsonify({"success": False, "error": "No hay campos para actualizar"}), 400
        
        update_result = auth_client.table('ubicaciones').update(update_data).eq('usuario_id', user_uuid).execute()
        
        if not update_result.data or len(update_result.data) == 0:
            return jsonify({"success": False, "error": "No se pudo actualizar ubicaciones"}), 500
        
        return jsonify({
            "success": True,
            "message": "Ubicaciones actualizadas correctamente",
            "data": update_result.data
        })
        
    except Exception as e:
        logger.error(f"Error editando ubicaciones: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@edit_bp.route('/api/data/usuarios', methods=['GET'])
def get_usuario_data():
    """Obtener datos del usuario autenticado para el formulario de edición"""
    try:
        auth_client = get_authenticated_client()
        if not auth_client:
            return jsonify({"success": False, "error": "Error de autenticación"}), 401
        
        user_uuid = g.user.get('user_uuid')
        if not user_uuid:
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
        
        # Obtener datos del usuario
        usuario = auth_client.table('usuarios').select('*').eq('id', user_uuid).single().execute()
        if not usuario.data:
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
        
        # Obtener información de contacto
        info_contacto = auth_client.table('info_contacto').select('*').eq('usuario_id', user_uuid).single().execute()
        
        # Obtener ubicaciones
        ubicaciones = auth_client.table('ubicaciones').select('*').eq('usuario_id', user_uuid).single().execute()
        
        return jsonify({
            "success": True,
            "usuario": usuario.data,
            "info_contacto": info_contacto.data or {},
            "ubicaciones": ubicaciones.data or {}
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo datos de usuario: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@edit_bp.route('/api/edit/info_contacto', methods=['POST'])
def edit_info_contacto():
    """Editar información de contacto del usuario"""
    try:
        auth_client = get_authenticated_client()
        if not auth_client:
            return jsonify({"success": False, "error": "Error de autenticación"}), 401
        
        user_uuid = g.user.get('user_uuid')
        if not user_uuid:
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Datos requeridos"}), 400
        
        # Actualizar información de contacto
        update_data = {k: v for k, v in data.items() if k in ['correo_principal', 'telefono_principal', 'correo_secundario']}
        
        if not update_data:
            return jsonify({"success": False, "error": "No hay campos para actualizar"}), 400
        
        update_result = auth_client.table('info_contacto').update(update_data).eq('usuario_id', user_uuid).execute()
        
        if not update_result.data or len(update_result.data) == 0:
            return jsonify({"success": False, "error": "No se pudo actualizar información de contacto"}), 500
        
        return jsonify({
            "success": True,
            "message": "Información de contacto actualizada correctamente",
            "data": update_result.data
        })
        
    except Exception as e:
        logger.error(f"Error editando info_contacto: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
