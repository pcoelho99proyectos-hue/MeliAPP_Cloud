# 🐝 MeliAPP v3 - Sistema de Gestión Apícola

## 📋 Descripción General

MeliAPP v2 es una plataforma web integral para la gestión de operaciones apícolas, construida con Flask y Supabase. La aplicación incluye un sistema completo de autenticación con Google OAuth, búsquedas avanzadas, generación de códigos QR, gestión de lotes de miel, clasificación botánica, y una arquitectura modular basada en blueprints de Flask.

## 🏗️ Arquitectura del Sistema

### **Stack Tecnológico**
- **Backend**: Flask (Python 3.11+)
- **Base de Datos**: Supabase (PostgreSQL) con RLS
- **Frontend**: HTML5 + Tailwind CSS + Alpine.js + JavaScript
- **Autenticación**: Supabase Auth + Google OAuth + Session management
- **QR Codes**: Biblioteca segno para generación
- **API**: RESTful endpoints con soporte JSON
- **Deployment**: Vercel con configuración optimizada
- **Maps**: Google Maps API con Plus Codes

### **Arquitectura Modular (Blueprints)**

La aplicación está organizada en módulos independientes usando Flask Blueprints:

```
MeliAPP_v2/
├── app.py                          # Aplicación principal Flask + registro de blueprints
├── 
├── 📁 MÓDULOS DE AUTENTICACIÓN
├── auth_manager.py                 # Clase AuthManager centralizada
├── auth_manager_routes.py          # Blueprint: rutas de autenticación (/login, /register, OAuth)
├── 
├── 📁 MÓDULOS DE BÚSQUEDA Y PERFILES
├── searcher.py                     # Clase Searcher para búsquedas avanzadas
├── searcher_routes.py              # Blueprint: rutas de búsqueda y QR de usuarios
├── profile_routes.py               # Blueprint: visualización de perfiles
├── 
├── 📁 MÓDULOS DE GESTIÓN DE LOTES
├── lotes_manager.py                # Clase LotesManager para gestión de lotes
├── lotes_routes.py                 # Blueprint: API y web routes para lotes
├── 
├── 📁 MÓDULOS DE DATOS Y TABLAS
├── data_tables_supabase.py         # Operaciones genéricas de tablas
├── data_tables_routes.py           # Blueprint: endpoints de tablas con paginación
├── supabase_client.py              # Cliente Supabase singleton
├── supabase_client_routes.py       # Blueprint: rutas de prueba de conexión
├── 
├── 📁 MÓDULOS DE EDICIÓN Y MODIFICACIÓN
├── edit_user_data.py               # Blueprint: edición de datos de usuario
├── modify_DB.py                    # Clase DatabaseModifier para operaciones DB
├── 
├── 📁 MÓDULOS AUXILIARES
├── botanical_chart.py              # Blueprint: clasificación botánica por comuna
├── gmaps_utils.py                  # Utilidades para Google Maps y Plus Codes
├── web_routes.py                   # Blueprint: rutas web básicas (home, auth-test)
├── 
├── 📁 GENERACIÓN DE QR
├── qr_code/
│   ├── __init__.py
│   └── generator.py                # Generador de códigos QR con segno
├── 
├── 📁 FRONTEND
├── static/
│   └── js/
│       ├── botanical-chart.js      # Visualización de clases botánicas
│       ├── lotes-carousel.js       # Carrusel de lotes con scroll
│       └── oauth-handler.js        # Manejo de OAuth en frontend
├── templates/
│   ├── base/
│   │   └── layout.html             # Layout base con menú móvil
│   ├── pages/
│   │   ├── home.html               # Página principal
│   │   ├── profile.html            # Perfil de usuario con QR
│   │   ├── edit_profile.html       # Edición de perfil
│   │   ├── gestionar_lote.html     # Gestión de lotes
│   │   └── auth/
│   │       └── oauth-callback.html # Callback OAuth
│   └── components/
│       └── search-form.html        # Formulario de búsqueda
├── 
├── 📁 DOCUMENTACIÓN Y CONFIGURACIÓN
├── docs/
│   ├── README.md                   # Documentación completa
│   ├── clases.csv                  # Datos de clasificación botánica
│   └── VERCEL_DEPLOYMENT.md       # Guía de despliegue
├── requirements.txt                # Dependencias Python
├── runtime.txt                     # Versión Python para Vercel
├── vercel.json                     # Configuración Vercel
├── .vercelignore                   # Archivos ignorados en deploy
└── .gitignore                      # Archivos ignorados por Git
```

## 🚀 Instalación y Configuración

### Prerrequisitos
- Python 3.11 o superior
- Cuenta de Supabase
- Credenciales de Google OAuth (opcional)

### Pasos de Instalación

1. **Clona el repositorio:**
   ```bash
   git clone <repository-url>
   cd MeliAPP_v3
   ```

2. **Crea un entorno virtual:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Windows: .\venv\Scripts\activate
   ```

3. **Instala las dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configura las variables de entorno:**
   Crea un archivo `.env` en la raíz del proyecto:
   ```env
   # Supabase Configuration
   SUPABASE_URL=tu_url_de_supabase
   SUPABASE_KEY=tu_clave_anon_de_supabase
   SUPABASE_SERVICE_ROLE_KEY=tu_service_role_key
   
   # Flask Configuration
   SECRET_KEY=tu_clave_secreta_flask
   FLASK_ENV=development
   FLASK_DEBUG=1
   
   # Google OAuth (Opcional)
   GOOGLE_CLIENT_ID=tu_google_client_id
   GOOGLE_CLIENT_SECRET=tu_google_client_secret
   ```

## 🏃 Ejecución

### Desarrollo Local
```bash
python app.py
```
La aplicación estará disponible en `http://localhost:3000`

### Producción (Vercel)
```bash
vercel --prod
```

## 🌐 API Endpoints Completa

### 🔐 Autenticación (auth_manager_routes.py)
**Rutas Web:**
- `GET /login` - Página de inicio de sesión
- `POST /login` - Procesar login manual
- `GET /logout` - Cerrar sesión
- `GET /register` - Página de registro
- `POST /register` - Procesar registro manual
- `GET /edit-profile` - Página de edición de perfil

**OAuth:**
- `GET /api/auth/google` - Iniciar OAuth con Google
- `GET /auth/callback` - Callback OAuth de Google
- `POST /auth/callback-js` - Callback OAuth asíncrono

**API Endpoints:**
- `POST /api/login` - Login vía API
- `POST /api/auth/login` - Login alternativo
- `POST /api/register` - Registro vía API
- `POST /api/auth/register` - Registro alternativo
- `POST /api/auth/logout` - Logout vía API
- `GET /api/auth/session` - Verificar sesión activa

### 🔍 Búsqueda y Usuarios (searcher_routes.py)
**API Endpoints:**
- `GET /api/sugerir` - Sugerencias de autocompletado
- `GET /api/usuario/<user_id>` - Datos completos de usuario
- `GET /api/usuario/<user_id>/qr` - Código QR de usuario

**Rutas Web:**
- `GET /buscar` - Página de búsqueda avanzada
- `GET /usuario/<uuid_segment>/qr` - QR de usuario (requiere auth)

### 👤 Perfiles (profile_routes.py)
- `GET /profile/<user_id>` - Perfil público de usuario

### 🍯 Gestión de Lotes (lotes_routes.py)
**API Endpoints:**
- `POST /api/lotes/crear` - Crear nuevo lote
- `PUT /api/lotes/<lote_id>/actualizar` - Actualizar lote
- `DELETE /api/lotes/<lote_id>/eliminar` - Eliminar lote
- `GET /api/lotes/usuario/<auth_user_id>` - Lotes de usuario
- `GET /api/lotes/<lote_id>/composicion` - Composición de lote
- `GET /api/lotes/<lote_id>/qr` - QR de lote (requiere auth)

**Rutas Web:**
- `GET /gestionar-lote` - Página de gestión de lotes
- `GET /lote/<lote_id>/qr` - QR de lote (requiere auth)

**Debug:**
- `GET /debug/lotes/test-composicion` - Prueba de composición
- `GET /debug/lotes/test-crear` - Prueba de creación

### 📊 Tablas de Datos (data_tables_routes.py)
- `GET /api/table/<table_name>` - Datos de tabla con paginación
- `GET /api/tables` - Lista de tablas disponibles

### ✏️ Edición de Datos (edit_user_data.py)
- `POST /api/edit/usuarios` - Editar información de usuario
- `POST /api/edit/info_contacto` - Editar información de contacto
- `POST /api/edit/ubicaciones` - Editar ubicaciones
- `POST /api/edit/produccion_apicola` - Editar producción apícola
- `POST /api/edit/origenes_botanicos` - Editar orígenes botánicos
- `POST /api/edit/solicitudes_apicultor` - Editar solicitudes

### 🌿 Clasificación Botánica (botanical_chart.py)
- `GET /api/botanical-classes/<comuna>` - Clases botánicas por comuna
- `GET /api/botanical-classes` - Todas las clases botánicas

### 🔧 Sistema (supabase_client_routes.py)
- `GET /api/test` - Prueba de conexión con Supabase
- `GET /api/health` - Estado de salud del sistema

### 🏠 Rutas Web Básicas (web_routes.py)
- `GET /` - Página principal
- `GET /auth-test` - Página de prueba de autenticación

## 🗄️ Esquema de Base de Datos

### Tablas Principales

**Tabla `usuarios`** (Información básica de usuarios)
- `id` (UUID) - Clave primaria
- `auth_user_id` (UUID) - Referencia a auth.users(id)
- `username` (TEXT) - Nombre de usuario único
- `nombre_completo` (TEXT) - Nombre completo
- `created_at` (TIMESTAMP) - Fecha de creación
- `updated_at` (TIMESTAMP) - Última actualización

**Tabla `info_contacto`** (Información de contacto)
- `id` (UUID) - Clave primaria
- `auth_user_id` (UUID) - FK a auth.users(id)
- `email` (TEXT) - Correo electrónico
- `telefono` (TEXT) - Número de teléfono
- `direccion` (TEXT) - Dirección física

**Tabla `ubicaciones`** (Ubicaciones geográficas)
- `id` (UUID) - Clave primaria
- `auth_user_id` (UUID) - FK a auth.users(id)
- `nombre_ubicacion` (TEXT) - Nombre de la ubicación
- `latitud` (DECIMAL) - Coordenada latitud
- `longitud` (DECIMAL) - Coordenada longitud
- `plus_code` (TEXT) - Código Plus de Google
- `comuna` (TEXT) - Comuna
- `region` (TEXT) - Región

**Tabla `produccion_apicola`** (Datos de producción)
- `id` (UUID) - Clave primaria
- `auth_user_id` (UUID) - FK a auth.users(id)
- `tipo_produccion` (TEXT) - Tipo de producción
- `cantidad_colmenas` (INTEGER) - Número de colmenas
- `produccion_anual` (DECIMAL) - Producción anual en kg
- `temporada` (TEXT) - Temporada de producción

**Tabla `origenes_botanicos`** (Orígenes botánicos)
- `id` (UUID) - Clave primaria
- `auth_user_id` (UUID) - FK a auth.users(id)
- `especie_botanica` (TEXT) - Especie botánica
- `porcentaje_composicion` (DECIMAL) - Porcentaje en composición
- `ubicacion_id` (UUID) - FK a ubicaciones(id)

**Tabla `solicitudes_apicultor`** (Solicitudes de apicultores)
- `id` (UUID) - Clave primaria
- `auth_user_id` (UUID) - FK a auth.users(id)
- `tipo_solicitud` (TEXT) - Tipo de solicitud
- `estado` (TEXT) - Estado de la solicitud
- `fecha_solicitud` (TIMESTAMP) - Fecha de solicitud
- `descripcion` (TEXT) - Descripción detallada

### Características de la Base de Datos
- **RLS (Row Level Security)**: Habilitado en todas las tablas
- **Autenticación**: Integrada con Supabase Auth
- **Relaciones**: Todas las tablas referencian `auth.users(id)`
- **Cascading Deletes**: Configurado para mantener integridad
- **Índices**: Optimizados para búsquedas por usuario y ubicación

## 🎯 Funcionalidades Principales

### ✅ Características Implementadas

**🔐 Sistema de Autenticación Completo**
- Login manual con email/contraseña
- Integración con Google OAuth 2.0
- Gestión de sesiones persistentes
- Registro de nuevos usuarios
- Confirmación por email (Supabase Auth) **EN DESARROLLO AÚN**
- Decoradores de autenticación para rutas protegidas

**🔍 Búsqueda Avanzada**
- Búsqueda multi-tabla en tiempo real
- Autocompletado inteligente con sugerencias
- Búsqueda por username, nombre, email
- Filtros por ubicación y tipo de producción
- Resultados paginados y optimizados

**👤 Gestión de Perfiles**
- Perfiles públicos con información completa
- Edición en tiempo real de datos personales
- Información de contacto y ubicaciones
- Datos de producción apícola
- Orígenes botánicos de la miel

**📱 Códigos QR Seguros**
- Generación automática para usuarios y lotes
- Autenticación requerida para acceso
- Validación de propiedad de recursos
- Múltiples formatos (PNG, JSON)
- Escalado personalizable

**🍯 Gestión de Lotes de Miel**
- Creación, edición y eliminación de lotes
- Composición botánica detallada
- Orden manual personalizable
- Carrusel interactivo con scroll suave
- QR codes individuales por lote
- Validación de unicidad de orden

**🌿 Clasificación Botánica**
- Base de datos de especies por comuna
- Visualización interactiva de clases
- Integración con datos de producción
- Carga optimizada desde CSV
- Cache para mejor rendimiento

**📱 Diseño Responsive**
- Mobile-first con Tailwind CSS
- Menú móvil con Alpine.js
- Carruseles optimizados para touch
- Navegación adaptativa
- Componentes modulares reutilizables

**🗺️ Integración con Mapas**
- Google Maps API
- Soporte para Plus Codes
- Conversión automática de coordenadas
- Validación de ubicaciones
- Geocodificación inversa

## 🛠️ Dependencias y Tecnologías

### Dependencias Python (requirements.txt)
```
Flask                    # Framework web principal
python-dotenv           # Gestión de variables de entorno
pandas                  # Manipulación de datos
chardet                 # Detección de codificación
urllib3                 # Cliente HTTP
openlocationcode        # Soporte para Plus Codes de Google
segno                   # Generación de códigos QR
requests                # Cliente HTTP simplificado
httpx                   # Cliente HTTP asíncrono
supabase               # Cliente oficial de Supabase
```

### Tecnologías Frontend
- **Tailwind CSS**: Framework CSS utility-first
- **Alpine.js**: Framework JavaScript reactivo ligero
- **JavaScript Vanilla**: Para funcionalidades específicas
- **HTML5**: Estructura semántica moderna

### Servicios Externos
- **Supabase**: Base de datos PostgreSQL + Auth + RLS
- **Google OAuth**: Autenticación con Google
- **Google Maps API**: Mapas y geocodificación
- **Vercel**: Plataforma de deployment

### Herramientas de Desarrollo
- **Python 3.11+**: Lenguaje principal
- **Flask Blueprints**: Arquitectura modular
- **Logging**: Sistema de logs detallado
- **Environment Variables**: Configuración segura

## 🔧 Variables de Entorno

| Variable        | Descripción                                  | Requerido | Ejemplo |
|----------------|---------------------------------------------|-----------|----------|
| SUPABASE_URL   | URL del proyecto Supabase                 | ✅ Sí | `https://xxx.supabase.co` |
| SUPABASE_KEY   | Clave anon de Supabase                    | ✅ Sí | `eyJhbGciOiJIUzI1NiIs...` |
| SUPABASE_SERVICE_ROLE_KEY | Service role key | ✅ Sí | `eyJhbGciOiJIUzI1NiIs...` |
| SECRET_KEY     | Clave secreta Flask sessions | ✅ Sí | `tu-clave-secreta-segura` |
| GOOGLE_CLIENT_ID | ID cliente OAuth Google | ⚠️ Opcional | `123456789.apps.googleusercontent.com` |
| GOOGLE_CLIENT_SECRET | Secreto OAuth Google | ⚠️ Opcional | `GOCSPX-xxx` |
| FLASK_ENV      | Entorno de ejecución | ❌ No | `development` / `production` |
| FLASK_DEBUG    | Modo debug | ❌ No | `1` (activo) / `0` (inactivo) |
| VERCEL         | Indicador de Vercel | ❌ No | `1` (automático en Vercel) |

## 🚀 Deployment

### Vercel (Recomendado)

1. **Preparar el proyecto:**
   ```bash
   git clone <repository-url>
   cd MeliAPP_v2
   ```

2. **Instalar Vercel CLI:**
   ```bash
   npm install -g vercel
   ```

3. **Configurar variables de entorno:**
   ```bash
   vercel env add SUPABASE_URL
   vercel env add SUPABASE_KEY
   vercel env add SUPABASE_SERVICE_ROLE_KEY
   vercel env add SECRET_KEY
   vercel env add GOOGLE_CLIENT_ID
   vercel env add GOOGLE_CLIENT_SECRET
   ```

4. **Deploy a producción:**
   ```bash
   vercel --prod
   ```

### Desarrollo Local

1. **Activar entorno virtual:**
   ```bash
   source venv/bin/activate  # Linux/Mac
   .\venv\Scripts\activate   # Windows
   ```

2. **Ejecutar aplicación:**
   ```bash
   python app.py
   ```

3. **Acceder a la aplicación:**
   - URL: `http://localhost:3000`
   - Logs: Consola y archivo `meliapp_debug.log`

### Configuración de Producción

**Archivos de configuración incluidos:**
- `vercel.json` - Configuración de Vercel
- `runtime.txt` - Versión de Python
- `.vercelignore` - Archivos excluidos del deploy
- `requirements.txt` - Dependencias Python

## 🧪 Testing y Debug

### Endpoints de Debug Disponibles
- `GET /auth-test` - Prueba de autenticación
- `GET /api/test` - Prueba de conexión Supabase
- `GET /debug/lotes/test-composicion` - Prueba de composición de lotes
- `GET /debug/lotes/test-crear` - Prueba de creación de lotes

### Logs del Sistema
- **Archivo local**: `meliapp_debug.log`
- **Consola**: Logs en tiempo real durante desarrollo
- **Niveles configurados**: DEBUG para auth y DB operations

### Verificación de Funcionalidades
1. **Autenticación**: Probar login manual y OAuth
2. **Búsqueda**: Verificar autocompletado y resultados
3. **QR Codes**: Generar y validar códigos
4. **Lotes**: Crear, editar y eliminar lotes
5. **Perfiles**: Editar información de usuario

## 🔄 Arquitectura y Patrones

### Patrones Implementados
- **Singleton Pattern**: `SupabaseClient` para conexión única
- **Blueprint Pattern**: Modularización de rutas Flask
- **Decorator Pattern**: `@AuthManager.login_required`
- **Factory Pattern**: Generación de QR codes
- **Observer Pattern**: Logging centralizado

### Principios de Diseño
- **Separation of Concerns**: Cada módulo tiene responsabilidad específica
- **DRY (Don't Repeat Yourself)**: Código reutilizable
- **SOLID Principles**: Especialmente Single Responsibility
- **Security by Design**: Autenticación y validación en todas las capas

## 🤝 Contribución y Desarrollo

### Estructura para Nuevas Funcionalidades
1. **Crear nuevo Blueprint** en archivo separado
2. **Registrar en app.py** con `app.register_blueprint()`
3. **Documentar endpoints** en este README
4. **Agregar tests** en endpoints de debug
5. **Actualizar logs** para debugging

### Convenciones de Código
- **Nombres de archivos**: snake_case (ej: `auth_manager_routes.py`)
- **Nombres de clases**: PascalCase (ej: `AuthManager`)
- **Nombres de funciones**: snake_case (ej: `login_required`)
- **Blueprints**: sufijo `_bp` (ej: `auth_bp`)

## 📋 Información del Proyecto

- **Versión**: v2.0.0
- **Última actualización**: Enero 2025
- **Estado**: Producción estable
- **Licencia**: MIT
- **Arquitectura**: Modular con Flask Blueprints
- **Base de datos**: Supabase PostgreSQL con RLS
- **Deployment**: Vercel optimizado

## 📧 Soporte y Contacto

Para consultas técnicas o soporte:
- **Issues**: Crear issue en el repositorio
- **Documentación**: Ver archivos en `/docs/`
- **Logs**: Revisar `meliapp_debug.log` para debugging
- **Debug endpoints**: Usar rutas `/debug/` para pruebas

## REALIZADO POR: Rodrigo Jofré Cerda (rodrigojofre@udec.cl); SEPT - 2025.