# 🐝 MeliAPP v3 - Sistema de Gestión Apícola

## 📋 Descripción General

MeliAPP v3 es una plataforma web integral para la gestión de operaciones apícolas, construida con Flask y Supabase. Incluye gestión de usuarios, búsquedas avanzadas, generación de QR codes, y un sistema completo de clasificación botánica.

## 🏗️ Arquitectura del Sistema

### **Stack Tecnológico Actualizado**
- **Backend**: Flask (Python 3.8+)
- **Base de Datos**: Supabase (PostgreSQL 14+)
- **Frontend**: HTML5 + Tailwind CSS + JavaScript vanilla
- **Autenticación**: Supabase Auth + Google OAuth + Session management
- **QR**: Módulo segno para generación de códigos QR
- **API**: RESTful endpoints con soporte JSON
- **Deployment**: Vercel-ready con configuración optimizada

### **Estructura de Archivos Actualizada**

```
MeliAPP_v2/
├── app.py                          # Aplicación principal Flask
├── auth_manager.py                 # Gestión centralizada de autenticación
├── supabase_client.py             # Cliente Supabase singleton
├── searcher.py                    # Búsqueda avanzada multi-tabla
├── botanical_chart.py             # Sistema de clasificación botánica
├── data_tables_supabase.py        # Operaciones de tablas y serialización
├── routes.py                      # Endpoints API REST
├── edit_user_data.py              # Edición de datos de usuarios
├── modify_DB.py                   # Modificaciones de base de datos
├── gmaps_utils.py                 # Utilidades para Google Maps
├── qr_code/                       # Módulo de generación QR
│   ├── __init__.py
│   └── generator.py              # Generador de QR codes
├── services/                      # Servicios auxiliares
├── static/                        # Archivos estáticos
│   ├── css/
│   └── js/
│       ├── botanical-chart.js     # Visualización de clases botánicas
│       ├── profile-integration.js # Integración de perfiles
│       └── oauth-handler.js       # Manejo de OAuth
├── templates/                     # Plantillas HTML modulares
│   ├── base/
│   │   └── layout.html           # Layout base responsive
│   ├── pages/
│   │   ├── home.html
│   │   ├── edit_profile.html
│   │   └── gestionar_lote.html
│   ├── components/
│   └── auth/
├── docs/
│   ├── README.md                 # Documentación actualizada
│   ├── clases.csv               # Clasificación botánica
│   └── VERCEL_DEPLOYMENT.md     # Guía de despliegue
├── vercel.json                  # Configuración Vercel
├── requirements.txt             # Dependencias actualizadas
└── .gitignore                   # Archivos ignorados por Git
```

2. Crea un entorno virtual (recomendado):
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Windows: .\venv\Scripts\activate
   ```

3. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

4. Configura las variables de entorno:
   Crea un archivo `.env` en la raíz del proyecto con las siguientes variables:
   ```
   SUPABASE_URL=tu_url_de_supabase
   SUPABASE_KEY=tu_clave_de_api_supabase
   ```

## 🏃 Ejecución

Para iniciar la aplicación en modo desarrollo:

```bash
python app.py
```

La aplicación estará disponible en `http://localhost:3000`

## 🌐 Endpoints de la API Actualizados

### Autenticación y Sesión
- `GET /auth-test` - Verifica estado de autenticación
- `GET /auth/callback` - Callback de autenticación Google OAuth
- `POST /auth/callback-js` - Manejo asíncrono de autenticación

### Búsqueda y Usuarios
- `GET /` - Página principal con búsqueda
- `GET /buscar` - Interfaz de búsqueda avanzada
- `GET /sugerir` - Sugerencias de autocompletado
  - Parámetros: `q` (término de búsqueda)
- `GET /api/usuario/<uuid>` - Datos completos de usuario
- `GET /api/usuario/<uuid>/qr` - Genera código QR para perfil
  - Parámetros: `format` (png/json), `scale` (tamaño)

### Gestión de Datos
- `GET /api/test` - Prueba de conexión con Supabase
- `GET /api/tables` - Lista todas las tablas disponibles
- `GET /api/table/<table_name>` - Datos de tabla específica
- `POST /api/editar-usuario` - Actualización de datos de usuario
- `GET /api/botanical-classes/<comuna>` - Clasificación botánica por comuna

### Perfiles y Edición
- `GET /profile/<uuid>` - Perfil público de usuario
- `GET /editar-perfil` - Interfaz de edición de perfil
- `POST /guardar-perfil` - Guardar cambios de perfil
- `GET /gestionar-lote` - Gestión de lotes apícolas

## 🏗️ Estructura del Proyecto Actualizada

```
MeliAPP_v2/
├── app.py                          # Aplicación principal Flask
├── auth_manager.py                 # Gestión centralizada de autenticación
├── supabase_client.py             # Cliente Supabase singleton
├── searcher.py                    # Búsqueda avanzada multi-tabla
├── botanical_chart.py             # Sistema de clasificación botánica
├── data_tables_supabase.py        # Operaciones de tablas y serialización
├── routes.py                      # Endpoints API REST
├── edit_user_data.py              # Edición de datos de usuarios
├── modify_DB.py                   # Modificaciones de base de datos
├── gmaps_utils.py                 # Utilidades para Google Maps
├── debug_endpoint.py              # Endpoints de debug
├── supabase_client.py             # Cliente de base de datos
├── qr_code/                       # Módulo de generación QR
│   ├── __init__.py
│   └── generator.py              # Generador de QR codes
├── static/                        # Archivos estáticos
│   ├── css/
│   └── js/
│       ├── botanical-chart.js     # Visualización de clases botánicas
│       ├── profile-integration.js # Integración de perfiles
│       └── oauth-handler.js       # Manejo de OAuth
├── templates/                     # Plantillas HTML modulares
│   ├── base/
│   │   └── layout.html           # Layout base responsive
│   ├── pages/
│   │   ├── home.html
│   │   ├── edit_profile.html
│   │   ├── gestionar_lote.html
│   │   └── login.html
│   ├── components/
│   │   └── search-form.html
│   └── auth/
│       └── oauth-callback.html
├── docs/                          # Documentación
│   ├── README.md                 # Documentación actualizada
│   ├── clases.csv               # Clasificación botánica
│   └── VERCEL_DEPLOYMENT.md     # Guía de despliegue
├── vercel.json                  # Configuración Vercel
├── requirements.txt             # Dependencias actualizadas
├── .gitignore                   # Archivos ignorados por Git
├── .vercelignore               # Archivos ignorados por Vercel
└── runtime.txt                  # Versión de Python para Vercel
```

## 🗄️ Esquema de Base de Datos

### Tablas Principales
- **usuarios**: Información básica de usuarios
- **info_contacto**: Datos de contacto
- **ubicaciones**: Ubicaciones geográficas
- **produccion_apicola**: Datos de producción apícola
- **origenes_botanicos**: Orígenes botánicos de miel
- **solicitudes_apicultor**: Solicitudes de apicultores

### Características de Datos
- **Gestión completa** de perfiles de usuario
- **Sistema de QR codes** para identificación rápida
- **Clasificación botánica** por comunas y especies
- **Historial de producción** y ubicaciones
- **Sistema de solicitudes** y gestión de lotes

## 🚀 Características Actuales

### ✅ Funcionalidades Implementadas
- **Autenticación completa** con Google OAuth
- **Búsqueda avanzada** con autocompletado
- **Perfiles públicos** con QR codes
- **Edición de perfiles** en tiempo real
- **Sistema de clasificación botánica** visual
- **Responsive design** mobile-first
- **API RESTful** completa
- **Gestión de lotes apícolas**

### 📊 Visualización de Datos
- **Clases botánicas** por comuna
- **Mapas interactivos** con ubicaciones
- **Gráficos de producción**
- **Códigos QR** para compartir perfiles

## 🔧 Variables de Entorno Actualizadas

| Variable | Descripción | Requerido |
|----------|-------------|-----------|
| SUPABASE_URL | URL de proyecto Supabase | Sí |
| SUPABASE_KEY | Clave API de Supabase | Sí |
| SECRET_KEY | Clave secreta Flask sessions | Sí |
| GOOGLE_CLIENT_ID | ID cliente Google OAuth | Sí |
| GOOGLE_CLIENT_SECRET | Secreto cliente Google OAuth | Sí |
| FLASK_ENV | Entorno (development/production) | No |
| FLASK_DEBUG | Modo debug (1=activo) | No |

## 🛠️ Dependencias Actualizadas

```
Flask==2.3.3
supabase==2.0.0
python-dotenv==1.0.0
segno==1.5.2
Pillow==10.0.0
requests==2.31.0
Werkzeug==2.3.7
```

## 📱 Características Frontend

### Tecnologías
- **Tailwind CSS** para estilos responsive
- **JavaScript vanilla** para interactividad
- **Alpine.js** para estados dinámicos
- **QR codes** generados dinámicamente

### Componentes
- **Búsqueda inteligente** con sugerencias
- **Perfiles públicos** con información completa
- **Sistema de clases botánicas** visual
- **Formularios dinámicos** para edición
- **Mapas interactivos** con ubicaciones

## 🎯 Deployment

### Vercel (Recomendado)
```bash
# Instalación
git clone [repo-url]
cd MeliAPP_v2
pip install -r requirements.txt

# Variables de entorno
vercel env add SUPABASE_URL
vercel env add SUPABASE_KEY
vercel env add SECRET_KEY

# Deploy
vercel --prod
```

### Local Development
```bash
python app.py
# Acceder a: http://localhost:3000
```

## 🤝 Contribución

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles.

## 📧 Soporte

Para soporte técnico o consultas:
- Email: soporte@meliapp.cl
- GitHub Issues: [Crear issue](https://github.com/tu-usuario/MeliAPP_v2/issues)

## 🔄 Versionado

- **Versión actual**: v3.0.0
- **Última actualización**: Agosto 2025
- **Changelog**: Ver `CHANGELOG.md`

## 🔒 Variables de Entorno

| Variable        | Descripción                                  | Requerido |
|----------------|---------------------------------------------|-----------|
| SUPABASE_URL   | URL de tu proyecto Supabase                 | Sí        |
| SUPABASE_KEY   | Clave de API de Supabase                    | Sí        |
| FLASK_ENV      | Entorno de Flask (development/production)    | No        |
| FLASK_DEBUG    | Modo debug (1 para activar)                 | No        |


## 🛠️ Dependencias Principales

- Flask - Framework web
- python-dotenv - Manejo de variables de entorno
- supabase - Cliente de Python para Supabase

## 📝 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles.

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor, lee nuestras pautas de contribución antes de enviar un pull request.

## 📧 Contacto

Para consultas o soporte, por favor contacta al equipo de desarrollo.