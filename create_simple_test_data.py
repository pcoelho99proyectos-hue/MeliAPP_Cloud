#!/usr/bin/env python3
"""
Script simple para crear datos de prueba sin RLS
"""

import os
import uuid
from dotenv import load_dotenv
from supabase import create_client

def create_simple_test_data():
    """Crear datos de prueba simples"""
    
    # Cargar variables de entorno
    load_dotenv(".env")
    
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_KEY')  # Usar key normal
    
    if not url or not key:
        print("❌ Error: SUPABASE_URL y SUPABASE_KEY deben estar configurados")
        return
    
    print(f"🔗 Conectando a Supabase...")
    client = create_client(url, key)
    
    # UUIDs fijos para testing
    test_auth_users = [
        str(uuid.uuid4()),
        str(uuid.uuid4()),
        str(uuid.uuid4())
    ]
    
    # Crear registros en tabla usuarios
    test_users = [
        {
            'auth_user_id': test_auth_users[0],
            'username': 'cristian_apicultor',
            'tipo_usuario': 'Apicultor',
            'role': 'regular',
            'status': 'active',
            'activo': True
        },
        {
            'auth_user_id': test_auth_users[1],
            'username': 'maria_productora',
            'tipo_usuario': 'Productor',
            'role': 'regular', 
            'status': 'active',
            'activo': True
        },
        {
            'auth_user_id': test_auth_users[2],
            'username': 'carlos_distribuidor',
            'tipo_usuario': 'Distribuidor',
            'role': 'regular',
            'status': 'active',
            'activo': True
        }
    ]
    
    print("📝 Creando usuarios de prueba...")
    
    try:
        # Insertar usuarios
        usuarios_response = client.table('usuarios').insert(test_users).execute()
        print(f"✅ Usuarios creados: {len(usuarios_response.data)}")
        
        # Crear info_contacto correspondiente
        contact_info = []
        for i, user in enumerate(test_users):
            contact_info.append({
                'auth_user_id': user['auth_user_id'],
                'nombre_completo': user['username'].replace('_', ' ').title(),
                'nombre_empresa': f"Empresa {user['username'].split('_')[0].title()}",
                'correo_principal': f"{user['username']}@test.com",
                'telefono_principal': f'+5691234567{i}',
                'direccion': f'Dirección de prueba {i+1}23',
                'comuna': ['Santiago', 'Valparaíso', 'Concepción'][i],
                'region': ['Metropolitana', 'Valparaíso', 'Biobío'][i]
            })
        
        print("📞 Creando información de contacto...")
        contacto_response = client.table('info_contacto').insert(contact_info).execute()
        print(f"✅ Contactos creados: {len(contacto_response.data)}")
        
        # Verificar datos creados
        print("\n🔍 Verificando datos creados:")
        usuarios_count = client.table('usuarios').select('auth_user_id', count='exact').execute()
        contacto_count = client.table('info_contacto').select('auth_user_id', count='exact').execute()
        
        print(f"📊 Total usuarios: {usuarios_count.count}")
        print(f"📊 Total contactos: {contacto_count.count}")
        
        # Mostrar algunos datos
        sample_users = client.table('usuarios').select('*').limit(3).execute()
        print(f"\n👥 Usuarios de muestra:")
        for user in sample_users.data:
            print(f"  - {user['username']} ({user['tipo_usuario']}) - ID: {user['auth_user_id'][:8]}...")
        
        print("\n🎉 ¡Datos de prueba creados exitosamente!")
        print("Ahora puedes probar la búsqueda con términos como:")
        print("  - 'cr' → encontrará 'cristian_apicultor'")
        print("  - 'maria' → encontrará 'maria_productora'")
        print("  - 'carlos' → encontrará 'carlos_distribuidor'")
        
    except Exception as e:
        print(f"❌ Error creando datos: {str(e)}")
        print(f"Tipo de error: {type(e)}")

if __name__ == "__main__":
    create_simple_test_data()
