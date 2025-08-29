# Informe: Análisis del Sistema de Autenticación

Este documento detalla el funcionamiento del sistema de autenticación de MeliAPP, su integración con Supabase y las recomendaciones para mejorar su seguridad y funcionalidad.

### 1. Análisis del Sistema de Autenticación Actual

El sistema de autenticación está bien estructurado y centralizado en el módulo `auth_manager.py`, lo que facilita su mantenimiento.

*   **Flujo de Login y Registro**:
    *   **Registro**: El método `AuthManager.register_user` utiliza `db.client.auth.sign_up` para crear un nuevo usuario en Supabase. Inmediatamente después, crea un registro correspondiente en las tablas locales `usuarios` e `info_contacto`.
    *   **Login**: El método `AuthManager.login_user` usa `db.client.auth.sign_in_with_password` para validar las credenciales contra Supabase.
    *   **Sesión**: Tras un login o registro exitoso, se almacenan los tokens de sesión (JWT) en la sesión de Flask, manteniendo al usuario autenticado.

*   **Gestión de Contraseñas con Supabase**:
    *   Tu aplicación **no almacena ni procesa contraseñas**. Todo el manejo de credenciales se delega de forma segura a Supabase.
    *   Supabase utiliza algoritmos de *hashing* robustos para proteger las contraseñas, garantizando que nunca se almacenen en texto plano.

*   **Integración con Google OAuth**:
    *   El flujo de autenticación con Google está correctamente implementado, ofreciendo una alternativa segura y cómoda al login tradicional.

### 2. Recomendaciones Críticas y Funcionalidades Faltantes

Aunque el sistema es funcional, carece de dos características esenciales para cualquier aplicación moderna y no implementa una capa de seguridad fundamental.

#### **Recomendación 1: Implementar la Recuperación de Contraseña (Urgente)**

Actualmente, si un usuario olvida su contraseña, no hay forma de que pueda recuperarla.

*   **Plan de Acción**:
    1.  **Crear una ruta y vista** para que el usuario solicite el reseteo (ej. `/forgot-password`).
    2.  **Añadir un método en `AuthManager`** que llame a `db.client.auth.reset_password_for_email(email)`. Supabase se encargará de enviar el email con el enlace de recuperación.
    3.  **Crear una nueva página** a la que el usuario será redirigido desde el email para introducir su nueva contraseña.
    4.  **Implementar la ruta y el método** para actualizar la contraseña en Supabase usando `db.client.auth.update_user()`.

#### **Recomendación 2: Implementar la Actualización de Contraseña**

Un usuario autenticado debería poder cambiar su contraseña desde su perfil.

*   **Plan de Acción**:
    1.  **Añadir un formulario** en la página de `edit_profile.html` para que el usuario introduzca su nueva contraseña.
    2.  **Crear un endpoint API** (ej. `/api/user/update-password`) que reciba la nueva contraseña.
    3.  **Añadir un método en `AuthManager`** que utilice `db.client.auth.update_user()` para cambiar la contraseña del usuario actualmente logueado.

#### **Recomendación 3: Activar Row Level Security (RLS) (Crítico para Seguridad)**

La documentación de Supabase es clara: la `anon_key` es segura para exponer en el cliente **solo si RLS está activado**. Sin RLS, un atacante podría, potencialmente, acceder o modificar datos a los que no debería tener acceso.

*   **Plan de Acción**:
    1.  **Auditar todas las tablas** que contienen datos de usuario (`usuarios`, `info_contacto`, `ubicaciones`, etc.).
    2.  **Crear políticas de RLS** en la base de datos de Supabase para cada tabla. Por ejemplo, una política común es permitir que un usuario solo pueda leer o modificar sus propias filas.
        *Ejemplo de política RLS para la tabla `info_contacto`*:
        ```sql
        CREATE POLICY "Los usuarios pueden ver su propia informacion de contacto"
        ON info_contacto FOR SELECT
        USING (auth.uid() = auth_user_id);

        CREATE POLICY "Los usuarios pueden actualizar su propia informacion de contacto"
        ON info_contacto FOR UPDATE
        USING (auth.uid() = auth_user_id);
        ```

#### **Recomendación 4: Habilitar la Confirmación de Email**

En `auth_manager.py`, el registro de usuarios está configurado con `email_confirm: False`.

*   **Plan de Acción**:
    1.  **Cambiar la opción a `email_confirm: True`** dentro del método `register_user`.
    2.  Esto requerirá que el usuario verifique su correo electrónico antes de poder iniciar sesión, lo que previene la creación de cuentas con emails falsos y asegura un canal de comunicación válido.
