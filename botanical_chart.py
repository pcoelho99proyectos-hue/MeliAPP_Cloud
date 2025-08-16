import os
import csv
from flask import Blueprint, jsonify
from functools import lru_cache

botanical_bp = Blueprint('botanical', __name__)

@lru_cache(maxsize=128)
def read_botanical_classes():
    """Lee el archivo CSV y retorna un diccionario con clases por comuna"""
    csv_path = os.path.join(os.path.dirname(__file__), 'docs', 'clases.csv')
    classes_by_commune = {}
    
    try:
        # Usar latin-1 para manejar caracteres españoles
        with open(csv_path, 'r', encoding='latin-1') as f:
            reader = csv.DictReader(f, delimiter=';')
            
            for row in reader:
                comuna = row.get('Comuna', '').strip()
                clase = row.get('Clase', '').strip()
                especie = row.get('Nombre Comun', '').strip()
                
                if comuna and clase and especie:
                    if comuna not in classes_by_commune:
                        classes_by_commune[comuna] = {}
                    if clase not in classes_by_commune[comuna]:
                        classes_by_commune[comuna][clase] = []
                    if especie not in classes_by_commune[comuna][clase]:
                        classes_by_commune[comuna][clase].append(especie)
                        
    except Exception as e:
        print(f"❌ Error leyendo CSV: {e}")
        return {}
        
    return classes_by_commune

@botanical_bp.route('/api/botanical-classes/<comuna>')
def get_botanical_classes(comuna):
    """Obtener clases botánicas para una comuna específica."""
    try:
        classes_data = read_botanical_classes()
        
        if not classes_data:
            return jsonify({
                'success': False, 
                'message': 'No hay datos disponibles'
            })
        
        # Verificar si la comuna existe (limpiar espacios y saltos de línea)
        comuna = comuna.strip()
        if comuna not in classes_data:
            available_communes = sorted(classes_data.keys())
            print(f"❌ Comuna '{comuna}' no encontrada")
            print(f"✅ Comunas disponibles: {available_communes}")
            
            return jsonify({
                'success': False, 
                'message': f'Comuna no registrada: {comuna}',
                'available_communes': available_communes,
                'requested_comuna': comuna
            })

        # Mapeo completo de clases botánicas con iconos, colores y descripciones pedagógicas
        CLASES_BOTANICAS = {
            'Arbol': {
                'icono': '🌳',
                'color': '#22c55e',
                'titulo': 'Árboles',
                'descripcion': 'Plantas leñosas perennes de gran tamaño',
                'categoria': 'Leñosa',
                'altura': 'Mayor a 5 metros'
            },
            'Arbol/Arbusto': {
                'icono': '🌲',
                'color': '#16a34a',
                'titulo': 'Árboles/Arbustos',
                'descripcion': 'Plantas leñosas de tamaño variable',
                'categoria': 'Leñosa Mixta',
                'altura': '2-5 metros'
            },
            'Arbusto': {
                'icono': '🌿',
                'color': '#84cc16',
                'titulo': 'Arbustos',
                'descripcion': 'Plantas leñosas de tamaño mediano',
                'categoria': 'Leñosa',
                'altura': '1-2 metros'
            },
            'Hierba': {
                'icono': '🌱',
                'color': '#65a30d',
                'titulo': 'Hierbas',
                'descripcion': 'Plantas herbáceas sin estructura leñosa',
                'categoria': 'Herbácea',
                'altura': 'Menor a 1 metro'
            },
            'Arbusto/Hierba': {
                'icono': '🌾',
                'color': '#a3a3a3',
                'titulo': 'Arbustos/Hierbas',
                'descripcion': 'Plantas con características mixtas',
                'categoria': 'Mixta',
                'altura': 'Variable'
            },
            'Arbol/Hierba': {
                'icono': '🌴',
                'color': '#10b981',
                'titulo': 'Árboles/Hierbas',
                'descripcion': 'Combinación de características arbóreas y herbáceas',
                'categoria': 'Mixta',
                'altura': 'Variable'
            }
        }
        
        # Formatear respuesta con información visual completa
        classes = []
        for clase, especies in classes_data[comuna].items():
            clase_info = CLASES_BOTANICAS.get(clase, {
                'icono': '🌿',
                'color': '#6b7280',
                'titulo': clase,
                'descripcion': 'Clase botánica',
                'categoria': 'Otra',
                'altura': 'Variable'
            })
            
            classes.append({
                'clase': clase,
                'titulo': clase_info['titulo'],
                'icono': clase_info['icono'],
                'color': clase_info['color'],
                'descripcion': clase_info['descripcion'],
                'categoria': clase_info['categoria'],
                'altura': clase_info['altura'],
                'especies': especies,
                'cantidad': len(especies)
            })

        print(f"✅ Comuna '{comuna}' encontrada con {len(classes)} clases")
        return jsonify({
            'success': True,
            'classes': classes,
            'comuna': comuna,
            'total_classes': len(classes)
        })

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@botanical_bp.route('/api/botanical-classes')
def get_all_communes():
    """Endpoint para obtener todas las comunas disponibles"""
    try:
        classes_data = read_botanical_classes()
        available_communes = sorted(classes_data.keys())
        
        return jsonify({
            'success': True,
            'communes': available_communes,
            'total': len(available_communes)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
