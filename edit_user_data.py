from flask import Blueprint, request, jsonify, g
import logging
from modify_DB import db_modifier, update_user_data
from auth_manager import auth_manager

logger = logging.getLogger(__name__)

edit_bp = Blueprint('edit_user_data', __name__)

@edit_bp.route('/api/edit/usuarios', methods=['POST'])
@auth_manager.login_required
def edit_usuarios():
    """Editar información de usuario usando el módulo modify_DB"""
    try:
        logger.info("=== INICIANDO EDICIÓN DE USUARIO ===")
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Datos requeridos"}), 400
        
        # Obtener user_uuid desde g.user después de la autenticación
        user_uuid = g.user.get('id')
        if not user_uuid:
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
        
        logger.info(f"📦 Datos recibidos: {data}")
        logger.info(f"👤 UUID usuario: {user_uuid}")
        
        # Remove non-existent fields
        data = {k: v for k, v in data.items() if k not in ['updated_at', 'created_at', 'id']}
        
        # Filtrar solo campos válidos para usuarios
        valid_fields = ['username', 'tipo_usuario', 'role', 'empresa', 'status']
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        
        logger.info(f"🔍 Datos filtrados: {filtered_data}")
        
        # DEBUG: Verificar si hay campo role y su longitud
        if 'role' in filtered_data:
            original_role = str(filtered_data['role'])
            logger.info(f"📝 Campo role - Original: '{original_role}' ({len(original_role)} chars)")
        
        if not filtered_data:
            return jsonify({"success": False, "error": "No hay campos válidos para actualizar"}), 400
        
        # Usar la función update_user_data que incluye truncamiento de role
        logger.info(f"🔄 Llamando a update_user_data con datos: {filtered_data}")
        result, status_code = update_user_data(filtered_data, user_uuid)
        
        logger.info(f"✅ Resultado: {result}, Status: {status_code}")
        
        # Agregar URL del perfil si la actualización fue exitosa
        if result.get('success'):
            result['profile_url'] = f"/profile/{user_uuid}"
        
        return jsonify(result), status_code
        
    except Exception as e:
        logger.error(f"Error editando usuario: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@edit_bp.route('/api/edit/ubicaciones', methods=['POST'])
@auth_manager.login_required
def edit_ubicaciones():
    """Editar ubicaciones con conversión automática de Plus Code y debug exhaustivo"""
    try:
        logger.info("🗺️ [UBICACIONES] ===== INICIANDO PROCESO DE EDICIÓN =====")
        
        # DEBUG: Mostrar todos los headers y datos recibidos
        logger.info(f"🗺️ [UBICACIONES] Headers: {dict(request.headers)}")
        logger.info(f"🗺️ [UBICACIONES] Método: {request.method}")
        logger.info(f"🗺️ [UBICACIONES] Content-Type: {request.headers.get('Content-Type')}")
        
        data = request.get_json()
        logger.info(f"🗺️ [UBICACIONES] 📦 Datos RAW recibidos: {data}")
        logger.info(f"🗺️ [UBICACIONES] 📦 Tipo de datos: {type(data)}")
        logger.info(f"🗺️ [UBICACIONES] 📦 Keys disponibles: {list(data.keys()) if data else 'None'}")
        
        if not data:
            logger.error("🗺️ [UBICACIONES] ❌ No se recibieron datos JSON")
            return jsonify({"success": False, "error": "No se recibieron datos"}), 400
        
        # Importar el conversor de Plus Code
        from gmaps_utils import process_ubicacion_data
        logger.info("🗺️ [UBICACIONES] 📥 Importando gmaps_utils...")
        
        # DEBUG: Mostrar datos antes del procesamiento
        logger.info(f"🗺️ [UBICACIONES] 🔍 Datos ANTES de procesamiento:")
        for key, value in data.items():
            logger.info(f"  {key}: {value} ({type(value)})")
        
        # Procesar datos incluyendo conversión de Plus Code
        logger.info("🗺️ [UBICACIONES] ⚙️ Iniciando procesamiento con gmaps_utils...")
        processed_data = process_ubicacion_data(data)
        
        # DEBUG: Mostrar datos después del procesamiento
        logger.info(f"🗺️ [UBICACIONES] ✨ Datos DESPUÉS de procesamiento:")
        for key, value in processed_data.items():
            logger.info(f"  {key}: {value} ({type(value)})")
        
        # Validar campos requeridos después del procesamiento
        required_fields = ['nombre', 'latitud', 'longitud']
        missing_fields = []
        
        for field in required_fields:
            if field not in processed_data:
                missing_fields.append(field)
                logger.error(f"🗺️ [UBICACIONES] ❌ Campo '{field}' no existe en processed_data")
            elif not processed_data[field]:
                missing_fields.append(field)
                logger.error(f"🗺️ [UBICACIONES] ❌ Campo '{field}' está vacío: {processed_data[field]}")
            else:
                logger.info(f"🗺️ [UBICACIONES] ✅ Campo '{field}': {processed_data[field]} ({type(processed_data[field])})")
        
        if missing_fields:
            logger.error(f"🗺️ [UBICACIONES] ❌ Campos faltantes: {missing_fields}")
            return jsonify({"success": False, "error": f"Campos requeridos: {missing_fields}"}), 400
        
        user_uuid = g.user['id']
        logger.info(f"🗺️ [UBICACIONES] 👤 Usuario UUID: {user_uuid}")
        
        # Convertir tipos de datos
        try:
            lat = float(processed_data['latitud'])
            lng = float(processed_data['longitud'])
            logger.info(f"🗺️ [UBICACIONES] 📍 Coordenadas convertidas: lat={lat}, lng={lng}")
        except (ValueError, TypeError) as e:
            logger.error(f"🗺️ [UBICACIONES] ❌ Error convirtiendo coordenadas: {e}")
            return jsonify({"success": False, "error": f"Error convirtiendo coordenadas: {e}"}), 400
        
        # Preparar datos para actualización
        update_data = {
            'nombre': str(processed_data['nombre']).strip(),
            'latitud': lat,
            'longitud': lng,
            'gmaps_plus_code': str(processed_data.get('gmaps_plus_code', '')).strip(),
            'norma_geo': str(processed_data.get('norma_geo', 'WGS84')).strip(),
            'descripcion': str(processed_data.get('descripcion', '')).strip()
        }
        
        logger.info(f"🗺️ [UBICACIONES] 📤 Datos finales para actualización: {update_data}")
        
        # Actualizar o insertar
        logger.info("🗺️ [UBICACIONES] 💾 Intentando actualizar base de datos...")
        result = db_modifier.update_user_data(user_uuid, 'ubicaciones', update_data)
        
        if result:
            logger.info(f"🗺️ [UBICACIONES] ✅ ¡ÉXITO! Ubicación actualizada para usuario {user_uuid}")
            return jsonify({"success": True})
        else:
            logger.error(f"🗺️ [UBICACIONES] ❌ Error actualizando ubicación para usuario {user_uuid}")
            return jsonify({"success": False, "error": "Error al actualizar ubicación"}), 500
            
    except ValueError as e:
        logger.error(f"🗺️ [UBICACIONES] ❌ Error de validación: {e}")
        return jsonify({"success": False, "error": f"Formato inválido de coordenadas: {e}"}), 400
    except Exception as e:
        logger.error(f"🗺️ [UBICACIONES] 💥 Error crítico: {e}")
        logger.error(f"🗺️ [UBICACIONES] 💥 Traceback: {traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500

@edit_bp.route('/api/data/usuarios', methods=['GET'])
@auth_manager.login_required
def get_usuario_data():
    """Obtener datos del usuario autenticado para el formulario de edición"""
    try:
        user_uuid = g.user.get('id')
        if not user_uuid:
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
        
        # Obtener datos del usuario
        usuario = db_modifier.get_record('usuarios', user_uuid)
        if not usuario:
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
        
        # Obtener información de contacto
        info_contacto = db_modifier.get_record('info_contacto', user_uuid)
        
        # Obtener ubicaciones
        ubicaciones = db_modifier.get_record('ubicaciones', user_uuid)
        
        return jsonify({
            "success": True,
            "usuario": usuario,
            "info_contacto": info_contacto or {},
            "ubicaciones": ubicaciones or {}
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo datos de usuario: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@edit_bp.route('/api/data/ubicaciones', methods=['GET'])
@auth_manager.login_required
def get_ubicaciones_data():
    """Obtener ubicaciones del usuario autenticado"""
    try:
        user_uuid = g.user.get('id')
        if not user_uuid:
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
        
        # Obtener ubicaciones
        ubicaciones = db_modifier.get_records('ubicaciones', user_uuid)
        
        return jsonify({
            "success": True,
            "ubicaciones": ubicaciones or []
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo ubicaciones: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@edit_bp.route('/api/data/info_contacto', methods=['GET'])
@auth_manager.login_required
def get_info_contacto_data():
    """Obtener datos de info_contacto del usuario autenticado"""
    try:
        user_uuid = g.user.get('id')
        if not user_uuid:
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
        
        # Obtener información de contacto
        info_contacto = db_modifier.get_record('info_contacto', user_uuid)
        
        return jsonify({
            "success": True,
            "data": info_contacto or {}
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo datos de info_contacto: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@edit_bp.route('/api/edit/info_contacto', methods=['POST'])
@auth_manager.login_required
def edit_info_contacto():
    """Editar información de contacto del usuario usando el módulo modify_DB"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Datos requeridos"}), 400
        
        user_uuid = g.user.get('id')
        if not user_uuid:
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
        
        # Definir campos válidos para información de contacto
        valid_fields = ['nombre_completo', 'nombre_empresa', 'correo_principal', 'telefono_principal', 'correo_secundario', 'telefono_secundario', 'direccion', 'comuna', 'region', 'pais']
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        
        if not filtered_data:
            return jsonify({"success": False, "error": "No hay campos para actualizar"}), 400
        
        # Usar el módulo modify_DB para actualizar
        result, status_code = db_modifier.update_record('info_contacto', filtered_data, user_uuid)
        
        # Agregar URL de perfil al resultado (igual que usuarios)
        if result.get('success', False):
            result['profile_url'] = f"/profile/{user_uuid}"
        
        return jsonify(result), status_code
        
    except Exception as e:
        logger.error(f"Error editando info_contacto: {e}")
        return jsonify({"success": False, "error": str(e)}), 500