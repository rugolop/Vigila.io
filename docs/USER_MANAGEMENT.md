# Gestión de Usuarios - Vigila.io

## Descripción

Sistema de gestión de usuarios con control de permisos basado en roles (RBAC - Role-Based Access Control).

## Roles Disponibles

### 1. Superadmin
- **Acceso**: Todos los tenants
- **Permisos**:
  - Gestionar usuarios de cualquier tenant
  - Crear, editar y eliminar usuarios
  - Asignar cualquier rol, incluyendo superadmin
  - Acceso completo al sistema

### 2. Admin
- **Acceso**: Su propio tenant
- **Permisos**:
  - Gestionar usuarios de su tenant
  - Crear, editar y eliminar usuarios
  - Asignar roles: admin, operator, viewer (NO superadmin)
  - Gestión completa del tenant

### 3. Operator
- **Acceso**: Su tenant
- **Permisos**:
  - Ver cámaras y grabaciones
  - No puede gestionar usuarios

### 4. Viewer
- **Acceso**: Su tenant (solo visualización)
- **Permisos**:
  - Solo visualización en vivo
  - No puede gestionar usuarios

## Estructura de Archivos

### Backend
- `apps/backend/routers/user_management.py` - Endpoints de gestión de usuarios
- `apps/backend/routers/users.py` - Endpoint del usuario actual (/api/me)
- `apps/backend/models.py` - Modelos de datos (TenantUser, Tenant)

### Frontend
- `apps/web/components/user-management.tsx` - Componente principal de UI
- `apps/web/app/dashboard/users/page.tsx` - Página de gestión de usuarios
- `apps/web/hooks/use-tenant.tsx` - Hook con sistema de permisos

## API Endpoints

### Listar Usuarios
```http
GET /api/users
Headers: X-User-Id: {user_id}
Query: ?tenant_id={id} (solo superadmin)
```

**Respuesta:**
```json
[
  {
    "id": "user_123",
    "email": "user@example.com",
    "name": "John Doe",
    "tenant_id": 1,
    "tenant_name": "Acme Corp",
    "role": "admin",
    "is_active": true,
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

### Obtener Usuario
```http
GET /api/users/{user_id}
Headers: X-User-Id: {user_id}
```

**Respuesta:**
```json
{
  "id": "user_123",
  "email": "user@example.com",
  "name": "John Doe",
  "email_verified": true,
  "image": null,
  "tenant_id": 1,
  "tenant_name": "Acme Corp",
  "tenant_slug": "acme",
  "role": "admin",
  "all_locations_access": false,
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Actualizar Usuario
```http
PATCH /api/users/{user_id}
Headers: 
  X-User-Id: {user_id}
  Content-Type: application/json

Body:
{
  "name": "Jane Doe",
  "role": "operator",
  "all_locations_access": true,
  "is_active": true
}
```

### Eliminar Usuario
```http
DELETE /api/users/{user_id}
Headers: X-User-Id: {user_id}
```

**Nota:** Eliminar solo remueve el TenantUser. El usuario de Better Auth permanece y puede ser reasignado.

## Reglas de Negocio

### Validación de Roles

#### Admin puede:
- ✅ Ver usuarios de su tenant
- ✅ Editar usuarios de su tenant
- ✅ Eliminar usuarios de su tenant
- ✅ Asignar roles: admin, operator, viewer
- ❌ **NO** puede asignar rol superadmin
- ❌ **NO** puede gestionar usuarios de otros tenants

#### Superadmin puede:
- ✅ Ver usuarios de todos los tenants
- ✅ Editar cualquier usuario
- ✅ Eliminar cualquier usuario
- ✅ Asignar cualquier rol incluyendo superadmin
- ✅ Filtrar por tenant

### Restricciones
1. **Auto-eliminación**: Los usuarios no pueden eliminarse a sí mismos
2. **Creación**: Los usuarios deben registrarse primero en Better Auth antes de poder ser asignados a tenants
3. **Sincronización de roles**: 
   - El rol `superadmin` se almacena en la tabla `user` de Better Auth
   - Los demás roles se almacenan en `tenant_users`
   - El endpoint `/api/me` combina ambas fuentes

## Flujo de Uso

### Como Admin del Tenant

1. Navegar a **Dashboard > Usuarios**
2. Ver lista de usuarios del tenant
3. Editar usuario:
   - Click en menú (⋮) > Editar
   - Modificar nombre, rol, permisos
   - Guardar cambios
4. Eliminar usuario:
   - Click en menú (⋮) > Eliminar
   - Confirmar eliminación

### Como Superadmin

1. Navegar a **Dashboard > Usuarios**
2. Filtrar por tenant (opcional)
3. Gestionar usuarios de cualquier tenant
4. Puede asignar rol superadmin a otros usuarios

## Integración con Better Auth

El sistema utiliza dos tablas:

1. **`user`** (Better Auth):
   - Información de autenticación
   - Email, password, verificación
   - Rol `superadmin` (campo opcional)

2. **`tenant_users`** (Vigila.io):
   - Relación usuario-tenant
   - Roles dentro del tenant
   - Permisos específicos

### Sincronización

Cuando se consulta el rol del usuario:
1. Se verifica la tabla `user` primero
2. Si tiene rol `superadmin`, se usa ese
3. Si no, se obtiene el rol de `tenant_users`

## Permisos en la UI

La navegación y componentes usan el hook `useTenant`:

```typescript
const { hasPermission, isSuperAdmin, isAdmin } = useTenant()

// Verificar permiso
if (hasPermission("canManageUsers")) {
  // Mostrar UI de gestión de usuarios
}

// Verificar rol específico
if (isSuperAdmin) {
  // Mostrar opciones de superadmin
}
```

### Sidebar Dinámico

El sidebar oculta automáticamente elementos según permisos:

```typescript
{
  title: "Usuarios",
  url: "/dashboard/users",
  icon: Users,
  requiredPermission: "canManageUsers", // Solo admins+
}
```

## Próximos Pasos

### Crear Usuario (TODO)
Actualmente el botón "Invitar Usuario" está deshabilitado porque requiere:

1. **Integración con Better Auth API**:
   - Crear usuario en tabla `user`
   - Enviar email de verificación
   - Gestionar passwords

2. **Opciones**:
   - Sistema de invitaciones por email
   - Integración con OAuth (Google, Microsoft)
   - Auto-registro con aprobación de admin

### Mejoras Futuras

- [ ] Gestión de ubicaciones por usuario
- [ ] Historial de cambios de permisos
- [ ] Notificaciones de cambios de rol
- [ ] Bulk actions (activar/desactivar múltiples)
- [ ] Exportar lista de usuarios
- [ ] Logs de auditoría de acciones

## Testing

### Datos de prueba

1. Crear usuarios con diferentes roles en la base de datos
2. Modificar rol a `superadmin` directamente en tabla `user`:
   ```sql
   UPDATE "user" SET role = 'superadmin' WHERE email = 'admin@example.com';
   ```

3. Verificar comportamiento según rol

### Casos de prueba

- ✅ Admin ve solo usuarios de su tenant
- ✅ Admin puede editar usuarios de su tenant
- ✅ Admin no puede crear superadmin
- ✅ Superadmin ve todos los usuarios
- ✅ Superadmin puede filtrar por tenant
- ✅ Superadmin puede crear otros superadmins
- ✅ Usuario no puede eliminarse a sí mismo
- ✅ Sidebar muestra/oculta según permisos

## Troubleshooting

### Usuario no aparece en la lista

**Causa**: No está asignado a ningún tenant

**Solución**: Asignar manualmente:
```sql
INSERT INTO tenant_users (id, tenant_id, role, all_locations_access, is_active)
VALUES ('user_id', 1, 'viewer', false, true);
```

### Rol superadmin no se refleja

**Causa**: No está en la tabla `user` de Better Auth

**Solución**: 
```sql
UPDATE "user" SET role = 'superadmin' WHERE id = 'user_id';
```

Luego cerrar sesión y volver a iniciar.

### Error 403 al gestionar usuarios

**Causa**: Usuario no tiene permisos

**Verificar**: 
- Rol del usuario actual
- Tenant del usuario que intenta modificar
- Permisos en `ROLE_PERMISSIONS`
