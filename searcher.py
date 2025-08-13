from typing import Dict, List, Any, Optional, Union, Tuple
from supabase import Client as SupabaseClient
from dataclasses import dataclass
from data_tables_supabase import list_tables, get_table_data
import logging

# Configuración de logging
logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    table: str
    id: str
    data: Dict[str, Any]
    matches: Dict[str, str]  # field: matched_value

class Searcher:
    def __init__(self, supabase_client):
        """Inicializa el Searcher con el cliente de Supabase."""
        self.supabase = supabase_client
        self.search_fields = {
            'usuarios': ['id', 'nombre', 'apellido', 'telefono'],
            'info_contacto': ['id', 'correo_personal', 'telefono', 'direccion'],
            'pedidos': ['id', 'usuario_id', 'numero_pedido', 'estado'],
            'ubicaciones': ['id', 'usuario_id', 'nombre', 'descripcion', 'norma_geo'],
            'origenes_botanicos': ['id', 'produccion_id', 'descripcion_flora', 'sector_actividad', 'detalles_transhumancia', 'caracteristicas_organicas'],
            'solicitudes_apicultor': ['id', 'usuario_id', 'nombre_completo', 'nombre_empresa', 'region', 'comuna', 'telefono', 'status']
        }
        
    def get_uuid_segment(self, uuid_str: str) -> str:
        """
        Extrae el primer segmento (8 caracteres) de un UUID.
        
        Args:
            uuid_str: UUID completo
            
        Returns:
            str: Primeros 8 caracteres del UUID en minúsculas
            
        Ejemplo:
            '550e8400-e29b-41d4-a716-446655440000' -> '550e8400'
        """
        if not uuid_str or not isinstance(uuid_str, str):
            return ''
        # Tomar los primeros 8 caracteres del UUID (sin guiones)
        clean_uuid = uuid_str.split('-')[0].lower()
        return clean_uuid[:8] if clean_uuid else ''

    def get_user_data(self, user_id: str) -> tuple[dict, dict, list, list, list, list, str]:
        """
        Obtiene los datos de un usuario, su información de contacto, ubicaciones, 
        producciones apícolas, orígenes botánicos y solicitudes por ID.
        
        Args:
            user_id: ID del usuario a buscar
            
        Returns:
            tuple: (user_data, contact_data, locations, producciones, origenes_botanicos, solicitudes, error_message)
        """
        if not user_id:
            return None, None, [], [], [], [], "Se requiere un ID de usuario"
            
        try:
            # Obtener datos del usuario
            user_response = self.supabase.table('usuarios').select('*').eq('id', user_id).maybe_single().execute()
            if not user_response.data:
                return None, None, [], [], [], [], "Usuario no encontrado"
                
            user = user_response.data
            
            # Obtener información de contacto
            contact_response = self.supabase.table('info_contacto').select('*').eq('usuario_id', user_id).maybe_single().execute()
            contact = contact_response.data if contact_response.data else {}
            
            # Obtener ubicaciones
            locations_response = self.supabase.table('ubicaciones').select('*').eq('usuario_id', user_id).execute()
            locations = locations_response.data if hasattr(locations_response, 'data') else []
            
            # Obtener producciones apícolas
            producciones_response = self.supabase.table('produccion_apicola').select('*').eq('usuario_id', user_id).execute()
            producciones = producciones_response.data if hasattr(producciones_response, 'data') else []
            
            # Obtener orígenes botánicos (asumiendo que hay una relación con producciones)
            origenes_botanicos = []
            if producciones:
                for prod in producciones:
                    origenes_response = self.supabase.table('origenes_botanicos') \
                        .select('*') \
                        .eq('produccion_id', prod['id']) \
                        .execute()
                    if hasattr(origenes_response, 'data') and origenes_response.data:
                        origenes_botanicos.extend(origenes_response.data)
            
            # Obtener solicitudes del apicultor
            solicitudes_response = self.supabase.table('solicitudes_apicultor') \
                .select('*') \
                .eq('usuario_id', user_id) \
                .order('created_at', desc=True) \
                .execute()
            solicitudes = solicitudes_response.data if hasattr(solicitudes_response, 'data') else []
            
            return user, contact, locations, producciones, origenes_botanicos, solicitudes, ""
            
        except Exception as e:
            error_msg = f"Error al buscar usuario: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return None, None, [], [], [], [], error_msg
    
    def get_user_id_by_auth_id(self, auth_user_id: str) -> Optional[str]:
        """
        Obtiene el ID del usuario en la tabla 'usuarios' a partir del ID de autenticación.
        
        Args:
            auth_user_id: ID del usuario desde la autenticación (Supabase Auth)
            
        Returns:
            str: ID del usuario en la tabla 'usuarios' o None si no se encuentra
        """
        try:
            response = self.supabase.table('usuarios').select('id').eq('auth_user_id', auth_user_id).maybe_single().execute()
            if hasattr(response, 'data') and response.data:
                return response.data['id']
        except Exception as e:
            print(f"Error al buscar usuario por auth_user_id {auth_user_id}: {str(e)}")
        return None

    def get_tables(self) -> List[str]:
        """
        Obtiene la lista de tablas disponibles usando data_tables_supabase.
        
        Returns:
            List[str]: Lista de nombres de tablas disponibles
        """
        try:
            # Primero intentamos con data_tables_supabase
            success, tables = list_tables()
            
            if success and tables:
                return tables
                
            # Si falla, intentamos con una consulta directa a las tablas de información
            try:
                result = self.supabase.table('pg_tables')\
                                  .select('tablename')\
                                  .eq('schemaname', 'public')\
                                  .execute()
                if hasattr(result, 'data') and result.data:
                    return [table['tablename'] for table in result.data]
            except Exception:
                pass
                
            # Último recurso: usar las tablas definidas en search_fields
            return list(self.search_fields.keys())
            
        except Exception as e:
            print(f"Error al obtener tablas: {str(e)}")
            return list(self.search_fields.keys())

    def search_in_table(self, table: str, term: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Busca un término en todos los campos de búsqueda de una tabla específica.
        
        Args:
            table: Nombre de la tabla donde buscar
            term: Término de búsqueda
            limit: Límite de resultados a devolver
            
        Returns:
            Lista de diccionarios con los resultados de la búsqueda
        """
        results = []
        try:
            # Obtener campos de búsqueda para esta tabla
            # 1. Usar campos predefinidos si existen
            if table in self.search_fields:
                fields = self.search_fields[table]
            else:
                # 2. Intentar obtener los campos de la tabla
                try:
                    result = self.supabase.table(table).select('*').limit(1).execute()
                    if hasattr(result, 'data') and result.data:
                        fields = list(result.data[0].keys())
                    else:
                        # 3. Usar campos comunes como último recurso
                        fields = ['id', 'nombre', 'correo_personal', 'descripcion']
                except Exception as e:
                    print(f"Error al obtener campos para la tabla {table}: {str(e)}")
                    fields = ['id', 'nombre', 'correo_personal', 'descripcion']
            
            if not fields:
                print(f"No se encontraron campos de búsqueda para la tabla {table}")
                return results
                
            # Construir consulta OR para buscar en múltiples campos
            query = self.supabase.table(table).select('*')
            
            # Añadir condiciones OR para cada campo
            or_conditions = []
            for field in fields:
                or_conditions.append(f"{field}.ilike.%{term}%")
            
            if or_conditions:
                query = query.or_(', '.join(or_conditions))
                
            # Aplicar límite y ejecutar consulta
            response = query.limit(limit).execute()
            
            if hasattr(response, 'data') and response.data:
                return response.data
                
        except Exception as e:
            print(f"Error al buscar en la tabla {table}: {str(e)}")
            
        return results

    async def search_in_all_tables(self, term: str, limit_per_table: int = 5) -> List[Dict[str, Any]]:
        """
        Busca un término en todas las tablas disponibles.
        
        Args:
            term: Término de búsqueda
            limit_per_table: Límite de resultados por tabla
            
        Returns:
            Lista de diccionarios con los resultados de la búsqueda
        """
        results = []
        try:
            tables = self.get_tables()
            for table in tables:
                try:
                    table_results = self.search_in_table(table, term, limit_per_table)
                    for result in table_results:
                        result['_table'] = table  # Agregar nombre de la tabla al resultado
                    results.extend(table_results)
                except Exception as e:
                    print(f"Error al buscar en la tabla {table}: {str(e)}")
                    continue
        except Exception as e:
            print(f"Error en búsqueda global: {str(e)}")
            
        return results

    async def find_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca un usuario por su ID en la tabla de usuarios.
        
        Args:
            user_id: ID del usuario a buscar
            
        Returns:
            Diccionario con los datos del usuario o None si no se encuentra
        """
        try:
            response = self.supabase.table('usuarios').select('*').eq('id', user_id).execute()
            if hasattr(response, 'data') and response.data:
                return response.data[0]
        except Exception as e:
            print(f"Error al buscar usuario por ID {user_id}: {str(e)}")
            
        return None

    async def find_contact_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca la información de contacto de un usuario por su ID.
        
        Args:
            user_id: ID del usuario
            
        Returns:
            Diccionario con la información de contacto o None si no se encuentra
        """
        try:
            response = self.supabase.table('info_contacto').select('*').eq('usuario_id', user_id).execute()
            if hasattr(response, 'data') and response.data:
                return response.data[0]
        except Exception as e:
            print(f"Error al buscar contacto para usuario {user_id}: {str(e)}")
            
        return None

    async def autocomplete(self, term: str, limit: int = 5) -> List[Dict[str, str]]:
        """
        Busca sugerencias de autocompletado en todos los campos relevantes.
        Devuelve una lista de sugerencias con el formato:
        [{"value": "valor", "label": "Etiqueta descriptiva"}, ...]
        """
        suggestions = []
        try:
            # Buscar en la tabla de usuarios
            users = self.search_in_table('usuarios', term, limit)
            for user in users:
                name = user.get('nombre', '')
                last_name = user.get('apellido', '')
                email = user.get('correo_personal', '')
                
                if name and last_name:
                    suggestions.append({
                        'value': user['id'],
                        'label': f"{name} {last_name} ({email})"
                    })
                elif email:
                    suggestions.append({
                        'value': user['id'],
                        'label': email
                    })
                
                if len(suggestions) >= limit:
                    break
                    
            # Si no hay suficientes resultados, buscar en info_contacto
            if len(suggestions) < limit:
                contacts = self.search_in_table('info_contacto', term, limit - len(suggestions))
                for contact in contacts:
                    email = contact.get('correo_personal', '')
                    phone = contact.get('telefono', '')
                    user_id = contact.get('usuario_id', '')
                    
                    if email and not any(s['value'] == user_id for s in suggestions):
                        suggestions.append({
                            'value': user_id,
                            'label': f"Contacto: {email} {f'({phone})' if phone else ''}"
                        })
                    
                    if len(suggestions) >= limit:
                        break
            
            return suggestions[:limit]
            
        except Exception as e:
            print(f"Error en autocompletar: {str(e)}")
            return []
            
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca un usuario por su ID y devuelve sus datos junto con la información de contacto.
        
        Returns:
            Diccionario con la estructura {
                'user': {datos_usuario},
                'contact': {datos_contacto} o None si no existe
            } o None si no se encuentra el usuario
        """
        try:
            # Buscar usuario
            user = await self.find_user_by_id(user_id)
            if not user:
                return None
                
            # Buscar información de contacto
            contact = await self.find_contact_by_user_id(user_id)
            
            return {
                'user': user,
                'contact': contact
            }
            
        except Exception as e:
            print(f"Error al buscar usuario por ID: {str(e)}")
            return None

    def obtener_esquema_tabla(self, tabla: str) -> List[Dict]:
        """Obtiene el esquema de una tabla específica."""
        try:
            # Usar el método table() para obtener información de la tabla
            response = self.supabase.table('information_schema.columns').select('*').eq('table_name', tabla).execute()
            return [{
                'column_name': col['column_name'],
                'data_type': col['data_type'],
                'is_nullable': col['is_nullable']
            } for col in response.data] if response.data else []
        except Exception as e:
            print(f"Error al obtener esquema de {tabla}: {str(e)}")
            return []

    def buscar_en_tabla(
        self, 
        tabla: str, 
        filtros: Optional[Dict] = None,
        orden_por: Optional[str] = None,
        ascendente: bool = True,
        limite: int = 100,
        pagina: int = 1
    ) -> Dict:
        """
        Busca registros en una tabla con filtros opcionales.
        
        Args:
            tabla: Nombre de la tabla
            filtros: Diccionario con {columna: valor} para filtrar
            orden_por: Columna para ordenar
            ascendente: Orden ascendente (True) o descendente (False)
            limite: Límite de resultados por página
            pagina: Número de página (1-based)
            
        Returns:
            Dict con los resultados y metadatos
        """
        try:
            offset = (pagina - 1) * limite
            query = self.supabase.table(tabla).select('*', count='exact')
            
            # Aplicar filtros
            if filtros:
                for columna, valor in filtros.items():
                    if valor:
                        query = query.ilike(columna, f'%{valor}%')
            
            # Aplicar ordenamiento
            if orden_por:
                query = query.order(orden_por, asc=ascendente)
            
            # Aplicar paginación
            query = query.range(offset, offset + limite - 1)
            
            # Ejecutar consulta
            resultado = query.execute()
            
            # Obtener total de registros
            total = len(resultado.data) if hasattr(resultado, 'count') and not resultado.count else resultado.count
            
            # Calcular total de páginas
            total_paginas = (total + limite - 1) // limite if limite > 0 else 1
            
            # Obtener esquema de la tabla
            esquema = self.obtener_esquema_tabla(tabla)
            
            # Obtener nombres de columnas del esquema
            columnas = [col['column_name'] for col in esquema] if esquema else (list(resultado.data[0].keys()) if resultado.data else [])
            
            return {
                'datos': resultado.data,
                'total': total,
                'total_paginas': total_paginas,
                'esquema': esquema,
                'columnas': columnas
            }
            
        except Exception as e:
            print(f"Error al buscar en tabla {tabla}: {str(e)}")
            return {
                'error': str(e),
                'datos': [],
                'total': 0,
                'total_paginas': 0,
                'esquema': [],
                'columnas': []
            }

    def obtener_por_id(self, tabla: str, id: str) -> Optional[Dict]:
        """Obtiene un registro por su ID."""
        try:
            query = self.supabase.table(tabla).select('*').eq('id', id).limit(1).execute()
            return query.data[0] if query.data else None
        except:
            return None
