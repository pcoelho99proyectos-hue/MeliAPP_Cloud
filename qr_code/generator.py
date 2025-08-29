"""
Generador de códigos QR para usuarios/apicultores utilizando la biblioteca segno.
"""
import segno
import base64
from io import BytesIO
from flask import url_for, current_app

class QRGenerator:
    def __init__(self, base_url=None):
        """
        Inicializa el generador de QR.
        
        Args:
            base_url: URL base para la redirección (opcional)
        """
        self.base_url = base_url
    
    def _get_user_url(self, uuid_segment):
        """Genera la URL para redirección del usuario."""
        if self.base_url:
            return f"{self.base_url}/api/usuario/{uuid_segment}"
        else:
            # Usar url_for si estamos en un contexto Flask
            return url_for('get_usuario_by_uuid_segment', 
                          uuid_segment=uuid_segment, 
                          _external=True)
    
    def generate_qr(self, user_id, navegador_supabase, scale=5, error_level='m'):
        """
        Genera un código QR para un usuario utilizando segno.
        
        Args:
            user_id: ID del usuario
            navegador_supabase: Instancia de NavegadorSupabase para obtener el segmento UUID
            scale: Factor de escala para el tamaño del QR
            error_level: Nivel de corrección de errores ('l', 'm', 'q', 'h')
            
        Returns:
            Objeto de QR de segno
        """
        # Extraer el segmento UUID usando el navegador
        uuid_segment = navegador_supabase.get_uuid_segment(user_id)
        
        if not uuid_segment:
            return None
            
        # Generar la URL
        url = self._get_user_url(uuid_segment)
        
        # Generar el código QR con una sola línea de código
        qr = segno.make(url, error=error_level)
        return qr
    
    def generate_qr_png(self, user_id, navegador_supabase, scale=5):
        """
        Genera un código QR en formato PNG.
        
        Args:
            user_id: ID del usuario
            navegador_supabase: Instancia de NavegadorSupabase
            scale: Factor de escala
            
        Returns:
            Bytes de la imagen PNG
        """
        qr = self.generate_qr(user_id, navegador_supabase)
        if not qr:
            return None
        return qr.png_bytes(scale=scale)
        
        if not qr:
            return None
            
        # Convertir a Base64
        png_data = qr.png_bytes(scale=scale)
        return f"data:image/png;base64,{base64.b64encode(png_data).decode()}"

def generate_qr_code(url, scale=5, border=2, error_level='m'):
    """
    Genera un código QR para una URL específica usando segno.

    Args:
        url (str): La URL para la cual se generará el QR.
        scale (int): Factor de escala para el tamaño del QR.
        border (int): El ancho del borde del QR.
        error_level (str): Nivel de corrección de errores ('l', 'm', 'q', 'h').

    Returns:
        Objeto de QR de segno.
    """
    # Generar el código QR con la configuración especificada
    qr = segno.make(url, error=error_level)
    # Se devuelve el objeto QR para que el llamador decida el formato (PNG, SVG, etc.)
    return qr
