from flask import Blueprint, request, jsonify, session, g
from auth_manager import AuthManager
from modify_DB import DatabaseModifier, update_user_data, update_user_contact
from supabase_client import SupabaseClient
import logging
import os
import csv


logger = logging.getLogger(__name__)
edit_bp = Blueprint('edit_user_data', __name__)

@edit_bp.route('/api/edit/usuarios', methods=['POST'])
@AuthManager.login_required
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
        # Agregar URL del perfil siempre usando el UUID del usuario autenticado
        if isinstance(result, dict) and result.get('success'):
            result['profile_url'] = f"/profile/{user_uuid}"
        
        return jsonify(result), status_code
        
    except Exception as e:
        logger.error(f"Error editando usuario: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@edit_bp.route('/api/edit/ubicaciones', methods=['POST', 'PUT', 'DELETE'])
@AuthManager.login_required
def handle_ubicaciones():
    """Manejar operaciones CRUD para ubicaciones con conversión automática de Plus Code"""
    try:
        method = request.method
        logger.info(f"🗺️ [UBICACIONES] ===== INICIANDO {method} =====")
        
        user_uuid = g.user.get('id')
        if not user_uuid:
            return jsonify({"success": False, "error": "Usuario no autenticado"}), 401
        
        if method == 'DELETE':
            # Eliminar ubicación
            data = request.get_json()
            location_id = data.get('id')
            
            if not location_id:
                return jsonify({"success": False, "error": "ID de ubicación requerido"}), 400
            
            # Verificar que la ubicación pertenece al usuario
            supabase = SupabaseClient()
            ubicaciones_response = supabase.client.table('ubicaciones').select('*').eq('auth_user_id', user_uuid).execute()
            ubicaciones = ubicaciones_response.data if ubicaciones_response.data else []
            ubicacion = next((u for u in ubicaciones if u.get('id') == location_id), None)
            
            if not ubicacion:
                return jsonify({"success": False, "error": "Ubicación no encontrada o no pertenece al usuario"}), 404
            
            result_response = supabase.client.table('ubicaciones').delete().eq('id', location_id).eq('auth_user_id', user_uuid).execute()
            success = bool(result_response.data)
            result = {"success": success, "message": "Ubicación eliminada exitosamente" if success else "Error al eliminar"}
            status_code = 200 if success else 400
            
            return jsonify(result), status_code
            
        elif method == 'POST':
            # Crear nueva ubicación
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "error": "Datos requeridos"}), 400
            
            # Importar el conversor de Plus Code
            from gmaps_utils import process_ubicacion_data
            processed_data = process_ubicacion_data(data)
            
            # Validar campos requeridos
            required_fields = ['nombre', 'latitud', 'longitud']
            missing_fields = [f for f in required_fields if f not in processed_data or not processed_data[f]]
            
            if missing_fields:
                return jsonify({"success": False, "error": f"Campos requeridos: {missing_fields}"}), 400
            
            # Preparar datos para inserción - solo columnas existentes
            insert_data = {
                'auth_user_id': user_uuid,
                'nombre': str(processed_data['nombre']).strip(),
                'latitud': float(processed_data['latitud']),
                'longitud': float(processed_data['longitud']),
                'norma_geo': str(processed_data.get('norma_geo', 'WGS84')).strip(),
                'descripcion': str(processed_data.get('descripcion', '')).strip()
            }
            
            result_response = supabase.client.table('ubicaciones').insert(insert_data).execute()
            success = bool(result_response.data)
            result = {"success": success, "data": result_response.data[0] if success else None}
            status_code = 201 if success else 400
            
            if result and isinstance(result, dict) and result.get('success'):
                result['profile_url'] = f"/profile/{user_uuid}"
            
            return jsonify(result), status_code
            
        elif method == 'PUT':
            # Actualizar ubicación existente
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "error": "Datos requeridos"}), 400
            
            location_id = data.get('id')
            if not location_id:
                return jsonify({"success": False, "error": "ID de ubicación requerido"}), 400
            
            # Verificar que la ubicación pertenece al usuario
            db_modifier = DatabaseModifier()
            ubicaciones = db_modifier.get_records('ubicaciones', user_uuid)
            ubicacion = next((u for u in ubicaciones if u.get('id') == location_id), None)
            
            if not ubicacion:
                return jsonify({"success": False, "error": "Ubicación no encontrada o no pertenece al usuario"}), 404
            
            # Importar el conversor de Plus Code
            from gmaps_utils import process_ubicacion_data
            processed_data = process_ubicacion_data(data)
            
            # Validar campos requeridos
            required_fields = ['nombre', 'latitud', 'longitud']
            missing_fields = [f for f in required_fields if f not in processed_data or not processed_data[f]]
            
            if missing_fields:
                return jsonify({"success": False, "error": f"Campos requeridos: {missing_fields}"}), 400
            
            # Preparar datos para actualización - solo columnas existentes
            update_data = {
                'nombre': str(processed_data['nombre']).strip(),
                'latitud': float(processed_data['latitud']),
                'longitud': float(processed_data['longitud']),
                'norma_geo': str(processed_data.get('norma_geo', 'WGS84')).strip(),
                'descripcion': str(processed_data.get('descripcion', '')).strip()
            }
            
            result_response = supabase.client.table('ubicaciones').update(update_data).eq('id', location_id).eq('auth_user_id', user_uuid).execute()
            success = bool(result_response.data)
            result = {"success": success, "data": result_response.data[0] if success else None}
            status_code = 200 if success else 400
            
            if result and isinstance(result, dict) and result.get('success'):
                result['profile_url'] = f"/profile/{user_uuid}"
            
            return jsonify(result), status_code
            
    except ValueError as e:
        logger.error(f"🗺️ [UBICACIONES] ❌ Error de validación: {e}")
        return jsonify({"success": False, "error": f"Formato inválido de coordenadas: {e}"}), 400
    except Exception as e:
        logger.error(f"🗺️ [UBICACIONES] 💥 Error crítico: {e}")
        import traceback
        logger.error(f"🗺️ [UBICACIONES] 💥 Traceback: {traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500

@edit_bp.route('/api/data/usuarios', methods=['GET'])
@AuthManager.login_required
def get_usuario_data():
    """Obtener datos del usuario autenticado para el formulario de edición"""
    try:
        # Obtener el UUID del usuario autenticado desde g.user
        user_uuid = g.user.get('id')
        if not user_uuid:
            return jsonify({"success": False, "error": "Usuario no autenticado"}), 401
            
        # Log para debugging
        logger.info(f"Usuario UUID obtenido: {user_uuid}")
        
        # Obtener datos del usuario
        supabase = SupabaseClient()
        
        # Obtener datos del usuario
        usuario_response = supabase.client.table('usuarios').select('*').eq('auth_user_id', user_uuid).single().execute()
        usuario = usuario_response.data if usuario_response.data else None
        if not usuario:
            return jsonify({"success": False, "error": "Usuario no encontrado en la base de datos"}), 404
            
        # Obtener información de contacto
        info_contacto_response = supabase.client.table('info_contacto').select('*').eq('auth_user_id', user_uuid).single().execute()
        info_contacto = info_contacto_response.data if info_contacto_response.data else {}
        
        # Obtener ubicaciones
        ubicaciones_response = supabase.client.table('ubicaciones').select('*').eq('auth_user_id', user_uuid).execute()
        ubicaciones = ubicaciones_response.data if ubicaciones_response.data else []
        
        return jsonify({
            "success": True,
            "usuario": usuario,
            "info_contacto": info_contacto or {},
            "ubicaciones": ubicaciones or {},
            "id": user_uuid  # UUID completo del usuario autenticado
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo datos de usuario: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@edit_bp.route('/api/edit/info_contacto', methods=['POST'])
@AuthManager.login_required
def edit_info_contacto():
    """Editar información de contacto del usuario usando el módulo modify_DB"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Datos requeridos"}), 400
        
        # Obtener el UUID del usuario autenticado
        user_uuid = g.user.get('id')
        if not user_uuid:
            return jsonify({"success": False, "error": "Usuario no autenticado"}), 401
            
        logger.info(f"Actualizando info_contacto para usuario: {user_uuid}")
        logger.info(f"Datos recibidos RAW: {data}")
        logger.info(f"Tipo de datos: {type(data)}")
        
        # Convertir todos los valores a strings y limpiar
        clean_data = {}
        for k, v in data.items():
            if v is not None:
                clean_data[k] = str(v).strip()
                logger.info(f"Campo {k}: '{v}' -> '{clean_data[k]}' (len: {len(clean_data[k])})")
        
        # Definir campos válidos
        valid_fields = ['nombre_completo', 'nombre_empresa', 'correo_principal', 'telefono_principal', 'correo_secundario', 'telefono_secundario', 'direccion', 'comuna', 'region', 'pais']
        
        # Filtrar campos válidos
        filtered_data = {k: v for k, v in clean_data.items() if k in valid_fields}
        logger.info(f"Campos válidos: {filtered_data}")
        
        # Verificar contenido real
        has_content = False
        for k, v in filtered_data.items():
            if v and str(v).strip():
                logger.info(f"Campo CON contenido: {k} = '{v}'")
                has_content = True
            else:
                logger.info(f"Campo SIN contenido: {k} = '{v}'")
        
        logger.info(f"¿Tiene contenido real?: {has_content}")
        
        if not has_content:
            return jsonify({"success": False, "error": "Por favor ingresa al menos un valor válido"}), 400
        
        # Solo enviar campos con contenido real
        final_data = {k: v for k, v in filtered_data.items() if v and str(v).strip()}
        logger.info(f"Datos finales para actualizar: {final_data}")
        
        # Usar la función específica para info_contacto
        result, status_code = update_user_contact(filtered_data, user_uuid)
        
        # Agregar URL del perfil siempre usando el UUID del usuario autenticado
        if isinstance(result, dict) and result.get('success', False):
            result['profile_url'] = f"/profile/{user_uuid}"
            result['user_id'] = user_uuid  # Asegurar que incluya el ID
            result['redirect_url'] = f"/profile/{user_uuid}"  # URL explícita para redirección
            logger.info(f"Redirección configurada: /profile/{user_uuid}")
        
        return jsonify(result), status_code
        
    except Exception as e:
        logger.error(f"Error editando info_contacto: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@edit_bp.route('/api/suggestions/comunas', methods=['GET'])
def get_comuna_suggestions():
    """Obtiene sugerencias de comunas desde clases.csv."""
    try:
        query = request.args.get('q', '').strip()
        if not query or len(query) < 2:
            return jsonify({'success': True, 'suggestions': []})
        
        csv_path = os.path.join(os.path.dirname(__file__), 'docs', 'clases.csv')
        comunas = set()
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file, delimiter=';')
                for row in reader:
                    comuna = row.get('Comuna', '').strip()
                    if comuna and query.lower() in comuna.lower():
                        # Capitalizar primera letra de cada palabra
                        comuna_capitalized = ' '.join(word.capitalize() for word in comuna.split())
                        comunas.add(comuna_capitalized)
        except FileNotFoundError:
            logger.warning(f"Archivo clases.csv no encontrado en {csv_path}")
            return jsonify({'success': True, 'suggestions': []})
        
        # Convertir a lista ordenada
        suggestions = sorted(list(comunas))[:10]  # Limitar a 10 sugerencias
        
        return jsonify({
            'success': True,
            'suggestions': suggestions
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo sugerencias de comunas: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500

@edit_bp.route('/api/suggestions/regiones', methods=['GET'])
def get_region_suggestions():
    """Obtiene sugerencias de regiones basadas en el término de búsqueda."""
    try:
        query = request.args.get('q', '').strip()
        if not query or len(query) < 2:
            return jsonify({'success': True, 'suggestions': []})
        
        supabase = SupabaseClient()
        
        # Buscar regiones en la tabla info_contacto
        response = supabase.client.table('info_contacto')\
            .select('region')\
            .ilike('region', f'%{query}%')\
            .not_.is_('region', 'null')\
            .neq('region', '')\
            .limit(10)\
            .execute()
        
        # Extraer regiones únicas y capitalizarlas
        regiones = set()
        if response.data:
            for item in response.data:
                region = item.get('region', '').strip()
                if region:
                    # Capitalizar primera letra de cada palabra
                    region_capitalized = ' '.join(word.capitalize() for word in region.split())
                    regiones.add(region_capitalized)
        
        # Convertir a lista ordenada
        suggestions = sorted(list(regiones))
        
        return jsonify({
            'success': True,
            'suggestions': suggestions
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo sugerencias de regiones: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500