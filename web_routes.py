"""
Módulo de rutas web básicas para MeliAPP_v2.

Este módulo contiene las rutas web generales:
- Página principal (home)
- Páginas de prueba y utilidades
- Rutas web que no pertenecen a módulos específicos
"""

import logging
from flask import Blueprint, render_template

logger = logging.getLogger(__name__)

# Crear blueprint para rutas web básicas
web_bp = Blueprint('web', __name__)

@web_bp.route('/')
def home():
    """
    Página principal con diseño moderno y llamadas a la acción.
    
    GET /
    """
    return render_template('pages/home.html')

@web_bp.route('/auth-test')
def auth_test():
    """
    Página de prueba para las rutas de autenticación API.
    
    GET /auth-test
    """
    return render_template('pages/auth_test.html')
