"use client"

import { useState, useEffect, useCallback, createContext, useContext, ReactNode } from "react"
import { useSession } from "@/lib/auth-client"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

// Tipos de roles
export type UserRole = "superadmin" | "admin" | "operator" | "viewer"

// Permisos por rol
export const ROLE_PERMISSIONS = {
  superadmin: {
    canViewLive: true,
    canViewRecordings: true,
    canManageCameras: true,
    canManageLocations: true,
    canManageTenants: true,
    canManageUsers: true,
    canManageStorage: true,
    canDeleteRecordings: true,
    canExportRecordings: true,
    canConfigureSettings: true,
    canAccessAllTenants: true,  // Acceso a TODOS los tenants
    canManageSystem: true,      // Configuración global del sistema
  },
  admin: {
    canViewLive: true,
    canViewRecordings: true,
    canManageCameras: true,
    canManageLocations: true,
    canManageTenants: false,    // Solo superadmin puede crear tenants
    canManageUsers: true,
    canManageStorage: true,
    canDeleteRecordings: true,
    canExportRecordings: true,
    canConfigureSettings: true,
    canAccessAllTenants: false,
    canManageSystem: false,
  },
  operator: {
    canViewLive: true,
    canViewRecordings: true,
    canManageCameras: true,
    canManageLocations: false,
    canManageTenants: false,
    canManageUsers: false,
    canManageStorage: false,
    canDeleteRecordings: false,
    canExportRecordings: true,
    canConfigureSettings: false,
    canAccessAllTenants: false,
    canManageSystem: false,
  },
  viewer: {
    canViewLive: true,
    canViewRecordings: false,
    canManageCameras: false,
    canManageLocations: false,
    canManageTenants: false,
    canManageUsers: false,
    canManageStorage: false,
    canDeleteRecordings: false,
    canExportRecordings: false,
    canConfigureSettings: false,
    canAccessAllTenants: false,
    canManageSystem: false,
  },
} as const

export type Permission = keyof typeof ROLE_PERMISSIONS.admin

// Interfaz del contexto
interface TenantContextValue {
  // Datos del usuario en el tenant
  tenantUser: TenantUser | null
  loading: boolean
  error: string | null
  
  // Helpers
  role: UserRole | null
  tenantId: number | null
  tenantName: string | null
  
  // Funciones de permisos
  hasPermission: (permission: Permission) => boolean
  isSuperAdmin: boolean
  isAdmin: boolean
  isOperator: boolean
  isViewer: boolean
  
  // Refetch
  refetch: () => Promise<void>
}

interface TenantUser {
  id: string
  tenant_id: number
  tenant_name: string
  tenant_slug: string
  role: UserRole
  all_locations_access: boolean
  is_active: boolean
}

// Contexto
const TenantContext = createContext<TenantContextValue | undefined>(undefined)

// Provider
interface TenantProviderProps {
  children: ReactNode
}

export function TenantProvider({ children }: TenantProviderProps) {
  const { data: session, isPending } = useSession()
  const [tenantUser, setTenantUser] = useState<TenantUser | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchTenantUser = useCallback(async () => {
    if (!session?.user?.id) {
      setTenantUser(null)
      setLoading(false)
      return
    }

    try {
      setLoading(true)
      setError(null)
      
      // Obtener información del usuario actual
      const response = await fetch(`${API_URL}/api/me`, {
        headers: {
          "X-User-Id": session.user.id,
        },
      })
      
      if (response.ok) {
        const data = await response.json()
        if (data) {
          setTenantUser(data)
          setLoading(false)
          return
        }
      }
      
      // Si no existe, asignar al tenant por defecto
      const assignResponse = await fetch(`${API_URL}/api/me/assign-to-tenant`, {
        method: "POST",
        headers: {
          "X-User-Id": session.user.id,
        },
      })
      
      if (assignResponse.ok) {
        // Volver a obtener el usuario
        const retryResponse = await fetch(`${API_URL}/api/me`, {
          headers: {
            "X-User-Id": session.user.id,
          },
        })
        
        if (retryResponse.ok) {
          const data = await retryResponse.json()
          if (data) {
            setTenantUser(data)
          }
        }
      }
      
      setLoading(false)
    } catch (err) {
      console.error("Error fetching tenant user:", err)
      setError("Error al cargar información del usuario")
      setLoading(false)
    }
  }, [session?.user?.id])

  useEffect(() => {
    if (!isPending) {
      fetchTenantUser()
    }
  }, [isPending, fetchTenantUser])

  const role = tenantUser?.role || null
  const tenantId = tenantUser?.tenant_id || null
  const tenantName = tenantUser?.tenant_name || null

  const hasPermission = useCallback((permission: Permission): boolean => {
    if (!role) return false
    return ROLE_PERMISSIONS[role][permission] ?? false
  }, [role])

  const value: TenantContextValue = {
    tenantUser,
    loading: loading || isPending,
    error,
    role,
    tenantId,
    tenantName,
    hasPermission,
    isSuperAdmin: role === "superadmin",
    isAdmin: role === "admin" || role === "superadmin",
    isOperator: role === "operator",
    isViewer: role === "viewer",
    refetch: fetchTenantUser,
  }

  return (
    <TenantContext.Provider value={value}>
      {children}
    </TenantContext.Provider>
  )
}

// Hook para usar el contexto
export function useTenant() {
  const context = useContext(TenantContext)
  if (context === undefined) {
    throw new Error("useTenant must be used within a TenantProvider")
  }
  return context
}

// Hook simplificado para permisos
export function usePermission(permission: Permission): boolean {
  const { hasPermission } = useTenant()
  return hasPermission(permission)
}

// Hook para verificar si el usuario tiene alguno de los roles especificados
export function useHasRole(...roles: UserRole[]): boolean {
  const { role } = useTenant()
  if (!role) return false
  return roles.includes(role)
}
