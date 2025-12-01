# 🔐 Configuración de Password Reset - MeliAPP

## ✅ Estado Actual

- ✅ **SMTP configurado**: Resend ya está activado
- ✅ **Backend listo**: Endpoints creados
- ✅ **Página web lista**: `/reset-password` funcionando
- ⚠️ **Falta configurar**: Template y Redirect URLs en Supabase

---

## 📋 Checklist de Configuración

### 1. ✅ Verificar Dominio en Resend

1. Ve a: https://resend.com/domains
2. Busca: **meliapp.cl**
3. Verifica que tenga status: ✅ **Verified**

**Si NO está verificado:**
- Agrega los registros DNS que Resend te indica
- Espera 5-10 minutos para propagación
- Verifica nuevamente

---

### 2. 🎨 Configurar Template de Password Recovery

**Paso 1:** En Supabase Dashboard, ve a:
```
Tu Proyecto → Authentication → Email Templates
```

**Paso 2:** Busca la sección **"Reset Password"**

**Paso 3:** Click en **"Edit"** o **"Customize"**

**Paso 4:** Reemplaza TODO el contenido con este template:

```html
<h2 style="color: #F59E0B; font-family: Arial, sans-serif;">Recuperar Contraseña - MeliAPP</h2>

<p style="font-family: Arial, sans-serif; color: #374151;">Hola,</p>

<p style="font-family: Arial, sans-serif; color: #374151;">
  Recibimos una solicitud para restablecer la contraseña de tu cuenta en MeliAPP.
</p>

<p style="font-family: Arial, sans-serif; color: #374151;">
  Haz clic en el siguiente botón para restablecer tu contraseña:
</p>

<div style="text-align: center; margin: 30px 0;">
  <a href="{{ .ConfirmationURL }}" 
     style="background-color: #F59E0B; 
            color: white; 
            padding: 12px 24px; 
            text-decoration: none; 
            border-radius: 6px; 
            display: inline-block;
            font-family: Arial, sans-serif;
            font-weight: bold;">
    Restablecer Contraseña
  </a>
</div>

<p style="font-family: Arial, sans-serif; color: #6B7280; font-size: 14px;">
  O copia y pega este enlace en tu navegador:
</p>
<p style="font-family: Arial, sans-serif; color: #6B7280; font-size: 12px; word-break: break-all;">
  {{ .ConfirmationURL }}
</p>

<hr style="border: none; border-top: 1px solid #E5E7EB; margin: 30px 0;">

<p style="font-family: Arial, sans-serif; color: #6B7280; font-size: 14px;">
  ⚠️ Si no solicitaste restablecer tu contraseña, puedes ignorar este correo de forma segura.
</p>

<p style="font-family: Arial, sans-serif; color: #374151; margin-top: 24px;">
  Saludos,<br>
  <strong>El equipo de MeliAPP</strong>
</p>

<div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #E5E7EB; font-family: Arial, sans-serif; font-size: 12px; color: #9CA3AF; text-align: center;">
  <p>MeliAPP - Gestión Profesional de Producción Apícola</p>
  <p>Este es un email automático, por favor no respondas a este mensaje.</p>
</div>
```

**Paso 5:** En "Subject", pon:
```
Restablecer tu Contraseña - MeliAPP
```

**Paso 6:** Click en **"Save"**

---

### 3. 🔗 Configurar Redirect URLs

**Paso 1:** En Supabase Dashboard, ve a:
```
Tu Proyecto → Authentication → URL Configuration
```

**Paso 2:** Busca "Site URL" y configura:
```
https://meli-app-cloud.vercel.app
```

**Paso 3:** Busca "Redirect URLs" y AGREGA estas URLs (click en "+ Add URL"):

```
https://meli-app-cloud.vercel.app/reset-password
https://meli-app-cloud.vercel.app/auth/callback
http://localhost:5000/reset-password
```

**IMPORTANTE:** NO borres URLs existentes, solo agrega las nuevas.

**Paso 4:** Click en **"Save"**

---

### 4. 🧪 Probar el Flujo Completo

#### **Desde el Backend (Web)**

1. **Solicitar Reset:**
   - Ve a: https://meli-app-cloud.vercel.app/login
   - Click en "¿Olvidaste tu contraseña?" (si existe)
   - O usa Postman:
     ```bash
     POST https://meli-app-cloud.vercel.app/api/auth/forgot-password
     Content-Type: application/json
     
     {
       "email": "tuemailreal@gmail.com"
     }
     ```

2. **Revisar Email:**
   - Abre tu bandeja de entrada
   - Busca email de: **noreply@meliapp.cl**
   - Subject: "Restablecer tu Contraseña - MeliAPP"

3. **Click en el Botón:**
   - Click en "Restablecer Contraseña"
   - Deberías llegar a: `https://meli-app-cloud.vercel.app/reset-password?token=...`

4. **Cambiar Contraseña:**
   - Ingresa nueva contraseña (mínimo 6 caracteres)
   - Confirma la contraseña
   - Click "Restablecer Contraseña"
   - Deberías ver mensaje de éxito

5. **Probar Login:**
   - Ve a: https://meli-app-cloud.vercel.app/login
   - Inicia sesión con tu nueva contraseña
   - ✅ Debería funcionar

#### **Desde Flutter App**

1. **Solicitar Reset:**
   - Abre la app Flutter
   - En LoginScreen, click "¿Olvidaste tu contraseña?"
   - Ingresa tu email
   - Click "Enviar"

2. **Revisar Email:**
   - Igual que arriba

3. **Click en Link:**
   - El link abrirá en el navegador (no en la app)
   - Completar el proceso en la web

4. **Probar Login en App:**
   - Vuelve a la app
   - Inicia sesión con la nueva contraseña
   - ✅ Debería funcionar

---

## 🔍 Troubleshooting

### ❌ No llega el email

**Verificar:**

1. **Dominio verificado en Resend**
   - https://resend.com/domains
   - Estado debe ser ✅ Verified

2. **Logs de Supabase**
   - Ve a: Authentication → Logs
   - Busca errores de "send_email"

3. **Bandeja de Spam**
   - Revisa carpeta de spam/correo no deseado

4. **Email correcto**
   - Asegúrate que el email esté registrado en Supabase Auth

### ❌ Token inválido o expirado

**Posibles causas:**

1. **Email viejo (>1 hora)**
   - Los tokens expiran en 1 hora
   - Solicita un nuevo email

2. **Token ya usado**
   - Cada token solo funciona 1 vez
   - Solicita nuevo reset

3. **Redirect URL incorrecta**
   - Verifica que `/reset-password` esté en Redirect URLs

### ❌ Error al cambiar contraseña

**Verificar:**

1. **Contraseña muy corta**
   - Mínimo 6 caracteres

2. **Contraseñas no coinciden**
   - Asegúrate de escribir igual en ambos campos

3. **Error de servidor**
   - Revisa logs de Vercel:
     ```bash
     vercel logs
     ```

---

## 📊 Logs para Debugging

### Backend (Vercel)

```bash
# Ver logs en tiempo real
vercel logs --follow

# Buscar logs específicos
vercel logs | grep "password"
vercel logs | grep "ERROR"
```

### Supabase

1. Ve a: **Logs** en sidebar
2. Busca eventos:
   - `auth.password_recovery_requested`
   - `auth.password_recovery_completed`
   - `mail.send`

### Resend

1. Ve a: https://resend.com/emails
2. Verifica que los emails se envíen
3. Revisa logs de cada email

---

## 🎯 Checklist Final

Antes de dar por terminado, verifica:

- [ ] Resend SMTP está habilitado en Supabase
- [ ] Dominio meliapp.cl está verificado en Resend
- [ ] Template de "Reset Password" está personalizado
- [ ] Site URL configurada: `https://meli-app-cloud.vercel.app`
- [ ] Redirect URLs agregadas (3 URLs)
- [ ] Email de prueba recibido exitosamente
- [ ] Link del email funciona correctamente
- [ ] Página `/reset-password` se carga sin errores
- [ ] Contraseña se cambia exitosamente
- [ ] Login con nueva contraseña funciona
- [ ] Probado desde Flutter app

---

## 🚀 Siguiente Paso: Deploy

Después de configurar todo:

```bash
cd c:\Users\askna\Documents\GitHub\MeliAPP_v2

# Commit cambios
git add auth_manager.py auth_manager_routes.py templates/pages/reset_password.html
git commit -m "feat: Password reset completo con Supabase y Resend

- Template de email personalizado
- Página web /reset-password
- Endpoint POST /api/auth/reset-password
- Logging mejorado para debugging
- Redirect URL configurada correctamente"

# Push a GitHub (Vercel hace deploy automático)
git push origin main
```

**Verificar deploy:**
- https://vercel.com/tu-usuario/meliapp-v2/deployments

**Probar en producción:**
- https://meli-app-cloud.vercel.app/reset-password

---

## 📞 Contacto

Si tienes problemas:
1. Revisa los logs (Vercel + Supabase + Resend)
2. Verifica cada paso del checklist
3. Asegúrate que el dominio esté verificado

---

**Autor:** Rodrigo Jofré Cerda  
**Fecha:** Diciembre 2025  
**Versión:** 1.0
