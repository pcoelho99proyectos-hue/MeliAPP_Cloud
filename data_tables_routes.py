"""
Módulo de rutas para operaciones de tablas de datos en MeliAPP_v2.

Este módulo contiene las rutas relacionadas con:
- Consulta de datos de tablas con paginación
- Listado de tablas disponibles
- Operaciones genéricas de base de datos
"""

import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

# Crear blueprint para rutas de tablas de datos
data_tables_bp = Blueprint('data_tables', __name__, url_prefix='/api')

@data_tables_bp.route('/table/<table_name>', methods=['GET'])
def get_table_data(table_name):
    """
    Obtiene datos de una tabla específica con paginación.
    
    GET /api/table/<table_name>?page=1&per_page=20
    """
    try:
        from data_tables_supabase import get_table_data as get_table_data_func
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        success, result = get_table_data_func(table_name, page, per_page)
        
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

@data_tables_bp.route('/tables', methods=['GET'])
def list_tables():
    """
    Lista todas las tablas disponibles en la base de datos.
    
    GET /api/tables
    """
    try:
        from data_tables_supabase import list_tables as list_tables_func
        success, result = list_tables_func()
        if success:
            return jsonify({"success": True, "tables": result})
        else:
            return jsonify({"success": False, "error": result}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
