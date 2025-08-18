"""
Módulo para manejar la conexión con Supabase.
"""
from supabase import create_client, Client
from dotenv import load_dotenv
import os
import httpx
import json

class SupabaseClient:
    _instance = None
    client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SupabaseClient, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Inicializa el cliente de Supabase."""
        # Intentar cargar variables de entorno desde .env (para desarrollo local)
        # Si no existe el archivo, continuar (para producción en Vercel)
        load_dotenv(".env")
        
        try:
            self.url = os.getenv('SUPABASE_URL')
            self.key = os.getenv('SUPABASE_KEY')
            
            print(f"[DEBUG SUPABASE] URL configurada: {bool(self.url)}")
            print(f"[DEBUG SUPABASE] KEY configurada: {bool(self.key)}")
            
            if not self.url or not self.key:
                raise ValueError("SUPABASE_URL y SUPABASE_KEY deben estar configurados")
            
            print(f"[DEBUG SUPABASE] Creando cliente con URL: {self.url[:30]}...")
            self.client = create_client(self.url, self.key)
            
            # Test de conexión
            try:
                test_response = self.client.table('usuarios').select('auth_user_id').limit(1).execute()
                print(f"[DEBUG SUPABASE] Test de conexión exitoso. Registros disponibles: {len(test_response.data) if test_response.data else 0}")
            except Exception as test_error:
                print(f"[DEBUG SUPABASE] WARNING - Test de conexión falló: {test_error}")
            
            print("✅ Cliente Supabase inicializado correctamente")
            
        except Exception as e:
            print(f"❌ Error inicializando cliente Supabase: {e}")
            raise ValueError(f"Error al conectar con Supabase: {str(e)}")
    
    def test_connection(self):
        """
        Prueba la conexión con Supabase.
        Solo verifica que las credenciales sean válidas y que se pueda establecer la conexión.
        No intenta acceder a ninguna tabla.
        """
        # Verificar que las credenciales existen
        if not self.url or not self.key:
            return False, "Error: Faltan credenciales de Supabase"
            
        # Verificar formato de credenciales
        if not self.url.startswith('http'):
            return False, f"Error: URL de Supabase inválida"
            
        if not self.key.startswith('ey'):
            return False, "Error: Clave de API de Supabase inválida"
            
        # Verificar que el cliente se inicializó
        if not hasattr(self, 'client') or not self.client:
            return False, "Error: No se pudo inicializar el cliente de Supabase"
            
        # Si llegamos aquí, la conexión es exitosa
        return True, f"Conexion exitosa a Supabase"
    
    def get_usuario(self, auth_user_id: str):
        """Obtiene un usuario por su auth_user_id (PRIMARY KEY)."""
        return self.client.table('usuarios').select('*').eq('auth_user_id', auth_user_id).maybe_single().execute()
    
    def get_contacto(self, auth_user_id: str):
        """Obtiene la información de contacto de un usuario."""
        return self.client.table('info_contacto').select('*').eq('auth_user_id', auth_user_id).maybe_single().execute()
    
    def get_ubicaciones(self, auth_user_id: str):
        """Obtiene las ubicaciones de un usuario."""
        return self.client.table('ubicaciones').select('*').eq('auth_user_id', auth_user_id).execute()
    
    def get_producciones_apicolas(self, auth_user_id: str):
        """Obtiene las producciones apícolas de un usuario."""
        return self.client.table('origenes_botanicos')\
            .select('*')\
            .eq('auth_user_id', auth_user_id)\
            .order('temporada', desc=True)\
            .execute()
    
    def get_origenes_botanicos(self, produccion_ids: list):
        """Obtiene los orígenes botánicos para una lista de IDs de producción."""
        if not produccion_ids:
            return []
        return self.client.table('origenes_botanicos')\
            .select('*')\
            .in_('produccion_id', produccion_ids)\
            .execute()
    
    def get_solicitudes_apicultor(self, auth_user_id: str):
        """Obtiene las solicitudes de apicultor de un usuario."""
        return self.client.table('solicitudes_apicultor')\
            .select('*')\
            .eq('auth_user_id', auth_user_id)\
            .order('created_at', desc=True)\
            .execute()
    
    async def invoke_edge_function(self, function_name: str, payload: dict):
        """
        Invoca una Edge Function de Supabase.
        
        Args:
            function_name (str): Nombre de la función Edge
            payload (dict): Datos a enviar
            
        Returns:
            dict: Respuesta de la función
        """
        try:
            # Construir la URL de la Edge Function
            edge_url = f"{self.url}/functions/v1/{function_name}"
            
            # Obtener el token de autenticación
            token = self.key
            
            # Headers para la petición
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'apikey': token
            }
            
            # Realizar la petición asíncrona
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    edge_url,
                    json=payload,
                    headers=headers
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    error_data = response.json() if response.content else {"error": "Error desconocido"}
                    raise Exception(f"Edge Function error: {error_data}")
                    
        except Exception as e:
            raise Exception(f"Error al invocar Edge Function: {str(e)}")
    
    def invoke_edge_function_sync(self, function_name: str, payload: dict):
        """
        Versión síncrona para invocar Edge Functions.
        
        Args:
            function_name (str): Nombre de la función Edge
            payload (dict): Datos a enviar
            
        Returns:
            dict: Respuesta de la función
        """
        try:
            import requests
            
            # Construir la URL de la Edge Function
            edge_url = f"{self.url}/functions/v1/{function_name}"
            
            # Obtener el token de autenticación
            token = self.key
            
            # Headers para la petición
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'apikey': token
            }
            
            # Realizar la petición síncrona
            response = requests.post(
                edge_url,
                json=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                error_data = response.json() if response.content else {"error": "Error desconocido"}
                raise Exception(f"Edge Function error: {error_data}")
                
        except Exception as e:
            raise Exception(f"Error al invocar Edge Function: {str(e)}")
    

# Instancia global
db = SupabaseClient()
