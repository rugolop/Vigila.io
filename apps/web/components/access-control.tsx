"use client"

import { ReactNode } from "react"
import { useTenant, Permission, UserRole, usePermission, useHasRole } from "@/hooks/use-tenant"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Card, CardContent } from "@/components/ui/card"
import { ShieldAlert, Loader2 } from "lucide-react"

interface RequirePermissionProps {
  permission: Permission
  children: ReactNode
  fallback?: ReactNode
  showAccessDenied?: boolean
}

/**
 * Componente que muestra contenido solo si el usuario tiene el permiso especificado.
 * 
 * @example
 * <RequirePermission permission="canManageCameras">
 *   <CameraSettings />
 * </RequirePermission>
 */
export function RequirePermission({ 
  permission, 
  children, 
  fallback,
  showAccessDenied = false 
}: RequirePermissionProps) {
  const { loading } = useTenant()
  const hasPermission = usePermission(permission)

  if (loading) {
    return fallback || null
  }

  if (!hasPermission) {
    if (showAccessDenied) {
      return <AccessDenied />
    }
    return fallback || null
  }

  return <>{children}</>
}

interface RequireRoleProps {
  roles: UserRole | UserRole[]
  children: ReactNode
  fallback?: ReactNode
  showAccessDenied?: boolean
}

/**
 * Componente que muestra contenido solo si el usuario tiene uno de los roles especificados.
 * 
 * @example
 * <RequireRole roles={["admin", "operator"]}>
 *   <ManageContent />
 * </RequireRole>
 */
export function RequireRole({ 
  roles, 
  children, 
  fallback,
  showAccessDenied = false 
}: RequireRoleProps) {
  const { loading } = useTenant()
  const roleArray = Array.isArray(roles) ? roles : [roles]
  const hasRole = useHasRole(...roleArray)

  if (loading) {
    return fallback || null
  }

  if (!hasRole) {
    if (showAccessDenied) {
      return <AccessDenied />
    }
    return fallback || null
  }

  return <>{children}</>
}

interface RequireAdminProps {
  children: ReactNode
  fallback?: ReactNode
  showAccessDenied?: boolean
}

/**
 * Componente que muestra contenido solo si el usuario es administrador o superadmin.
 */
export function RequireAdmin({ children, fallback, showAccessDenied = false }: RequireAdminProps) {
  return (
    <RequireRole roles={["admin", "superadmin"]} fallback={fallback} showAccessDenied={showAccessDenied}>
      {children}
    </RequireRole>
  )
}

/**
 * Componente que muestra contenido solo si el usuario es superadmin.
 * El superadmin tiene acceso a TODOS los tenants y configuración del sistema.
 */
export function RequireSuperAdmin({ children, fallback, showAccessDenied = false }: RequireAdminProps) {
  return (
    <RequireRole roles="superadmin" fallback={fallback} showAccessDenied={showAccessDenied}>
      {children}
    </RequireRole>
  )
}

/**
 * Componente que muestra un mensaje de acceso denegado.
 */
export function AccessDenied() {
  return (
    <Card className="border-destructive/50">
      <CardContent className="pt-6">
        <Alert variant="destructive">
          <ShieldAlert className="h-4 w-4" />
          <AlertTitle>Acceso Denegado</AlertTitle>
          <AlertDescription>
            No tienes permisos para acceder a esta sección. 
            Contacta con el administrador si crees que deberías tener acceso.
          </AlertDescription>
        </Alert>
      </CardContent>
    </Card>
  )
}

/**
 * Componente de carga para usar mientras se verifica el rol.
 */
export function RoleLoading() {
  const { loading } = useTenant()
  
  if (!loading) return null
  
  return (
    <div className="flex items-center justify-center p-8">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  )
}

/**
 * Hook que devuelve información del rol para mostrar en la UI.
 */
export function useRoleInfo() {
  const { role, isSuperAdmin, isAdmin, isOperator, isViewer } = useTenant()
  
  const getRoleLabel = () => {
    switch (role) {
      case "superadmin":
        return "Super Administrador"
      case "admin":
        return "Administrador"
      case "operator":
        return "Operador"
      case "viewer":
        return "Visualizador"
      default:
        return "Sin rol"
    }
  }
  
  const getRoleColor = () => {
    switch (role) {
      case "superadmin":
        return "text-purple-600 bg-purple-100"
      case "admin":
        return "text-red-600 bg-red-100"
      case "operator":
        return "text-blue-600 bg-blue-100"
      case "viewer":
        return "text-green-600 bg-green-100"
      default:
        return "text-gray-600 bg-gray-100"
    }
  }
  
  return {
    role,
    roleLabel: getRoleLabel(),
    roleColor: getRoleColor(),
    isSuperAdmin,
    isAdmin,
    isOperator,
    isViewer,
  }
}
