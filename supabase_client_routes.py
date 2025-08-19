"""
Módulo de rutas para operaciones específicas del SupabaseClient en MeliAPP_v2.

Este módulo contiene las rutas relacionadas con:
- Pruebas de conexión con Supabase
- Operaciones directas del cliente Supabase
"""

import logging
from flask import Blueprint, jsonify
from supabase_client import db

logger = logging.getLogger(__name__)

# Crear blueprint para rutas de SupabaseClient
supabase_bp = Blueprint('supabase', __name__, url_prefix='/api')

@supabase_bp.route('/test', methods=['GET'])
def test_connection():
    """
    Prueba la conexión con la base de datos Supabase.
    
    GET /api/test
    """
    try:
        # Usar función centralizada de test desde app.py
        from app import test_database_connection
        success, message = test_database_connection()
        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@supabase_bp.route('/test-db', methods=['GET'])
def test_db():
    """
    Prueba la conexión con la base de datos y devuelve información del sistema.
    
    GET /api/test-db
    """
    try:
        response = db.client.table('usuarios').select('auth_user_id').limit(1).execute()
        
        if response.data is not None:
            return jsonify({
                "success": True,
                "message": "Conexión exitosa con Supabase",
                "database_status": "online",
                "tables_count": len(response.data) if response.data else 0
            })
        else:
            return jsonify({
                "success": False,
                "error": "No se pudieron obtener datos de Supabase"
            }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Error de conexión: {str(e)}"
        }), 500
