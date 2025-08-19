"""
Módulo de rutas para perfiles de usuario en MeliAPP_v2.

Este módulo contiene las rutas relacionadas con:
- Visualización de perfiles de usuario
- Datos completos de perfil con información de contacto
- Integración con Searcher para búsqueda de usuarios
"""

import logging
from flask import Blueprint, render_template, url_for, redirect
from supabase_client import db
from searcher import Searcher

logger = logging.getLogger(__name__)

# Crear blueprint para rutas de perfiles
profile_bp = Blueprint('profile', __name__)

# Inicializar componentes
searcher = Searcher(db.client)

@profile_bp.route('/profile/<user_id>')
def profile(user_id):
    """
    Página de perfil de usuario con información completa y QR.
    
    GET /profile/<user_id>
    - user_id: Puede ser el UUID completo, segmento de 8 caracteres, o username
    """
    try:
        # Usar función centralizada para buscar usuario
        user_info = searcher.find_user_by_identifier(user_id)
        
        if not user_info:
            return render_template('pages/profile.html', error="Usuario no encontrado", user=None)
            
        user_uuid = user_info['auth_user_id']
        
        # Obtener información completa del usuario usando función centralizada
        profile_data = searcher.get_user_profile_data(user_uuid)
        
        if not profile_data:
            return render_template('pages/profile.html', error="Usuario no encontrado", user=None)
            
        # Si el ID proporcionado no es el UUID completo, redirigir
        if user_id != user_uuid:
            logger.info(f"Redirigiendo de {user_id} a {user_uuid}")
            return redirect(url_for('profile.profile', user_id=user_uuid))
            
        # Preparar datos para la plantilla
        user = profile_data['user']
        contact_info = profile_data['contact_info'] or {}
        locations = profile_data['locations']
        producciones = profile_data['production']
        origenes_botanicos = profile_data['botanical_origins']
        solicitudes = profile_data['requests']
        
        # Crear objeto user para la plantilla
        user_obj = {
            'id': user_uuid,
            'username': user.get('username', 'Usuario'),
            'nombre': user.get('nombre', ''),
            'apellido': user.get('apellido', ''),
            'email': contact_info.get('correo_principal', ''),
            'telefono': contact_info.get('telefono_principal', ''),
            'direccion': contact_info.get('direccion', ''),
            'comuna': contact_info.get('comuna', ''),
            'region': contact_info.get('region', ''),
            'nombre_empresa': contact_info.get('nombre_empresa', ''),
            'descripcion': user.get('descripcion', ''),
            'role': user.get('role', 'Apicultor'),
            'experiencia': user.get('experiencia', ''),
            'produccion_total': sum(p.get('cantidad_kg', 0) for p in producciones),
            'locations': locations,
            'producciones': producciones,
            'qr_url': url_for('search.get_user_qr', uuid_segment=user_uuid[:8], _external=True)
        }
        
        return render_template('pages/profile.html', 
                             user=user_obj,
                             contact_info=contact_info,
                             locations=locations,
                             production=producciones,
                             botanical_origins=origenes_botanicos,
                             requests=solicitudes,
                             qr_url=url_for('search.get_user_qr', uuid_segment=user_uuid[:8], _external=True))
        
    except Exception as e:
        logger.error(f"Error al cargar perfil: {str(e)}")
        return render_template('pages/profile.html', 
                             error="Error al cargar perfil",
                             user=None,
                             contact_info={},
                             locations=[],
                             production=[],
                             botanical_origins=[],
                             requests=[],
                             qr_url=None), 500
