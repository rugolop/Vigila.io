"use client"

import { useState, useEffect } from "react"
import { useTenant } from "@/hooks/use-tenant"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { 
  UserPlus, 
  MoreVertical, 
  Pencil, 
  Trash2, 
  Shield,
  ShieldCheck,
  Eye,
  Settings
} from "lucide-react"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"

// Types
interface User {
  id: string
  email: string
  name: string | null
  tenant_id: number
  tenant_name: string
  role: "superadmin" | "admin" | "operator" | "viewer"
  is_active: boolean
  created_at: string
}

interface UserDetail extends User {
  email_verified: boolean
  image: string | null
  tenant_slug: string
  all_locations_access: boolean
  updated_at: string
}

interface Tenant {
  id: number
  name: string
  slug: string
}

// Role configuration
const ROLE_CONFIG = {
  superadmin: {
    label: "Super Admin",
    icon: ShieldCheck,
    color: "text-purple-600 bg-purple-100",
    description: "Acceso completo a todos los tenants"
  },
  admin: {
    label: "Admin",
    icon: Shield,
    color: "text-blue-600 bg-blue-100",
    description: "Gestión completa del tenant"
  },
  operator: {
    label: "Operador",
    icon: Settings,
    color: "text-green-600 bg-green-100",
    description: "Acceso a grabaciones y live view"
  },
  viewer: {
    label: "Visualizador",
    icon: Eye,
    color: "text-gray-600 bg-gray-100",
    description: "Solo visualización en vivo"
  }
}

export function UserManagementComponent() {
  const { tenantUser, isSuperAdmin, loading: tenantLoading } = useTenant()
  const [users, setUsers] = useState<User[]>([])
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedTenant, setSelectedTenant] = useState<number | null>(null)
  
  // Dialog states
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [selectedUser, setSelectedUser] = useState<User | null>(null)
  
  // Form state
  const [formData, setFormData] = useState({
    name: "",
    role: "viewer" as "admin" | "operator" | "viewer" | "superadmin",
    tenant_id: 0,
    all_locations_access: false,
    is_active: true,
  })
  
  // Create user form state
  const [createFormData, setCreateFormData] = useState({
    email: "",
    name: "",
    password: "",
    role: "viewer" as "admin" | "operator" | "viewer" | "superadmin",
    tenant_id: 0,
    all_locations_access: false,
  })

  // Check permissions
  const canManageUsers = tenantUser?.role === "admin" || isSuperAdmin
  const canCreateSuperadmin = isSuperAdmin

  // Available roles based on current user
  const availableRoles = canCreateSuperadmin 
    ? ["superadmin", "admin", "operator", "viewer"]
    : ["admin", "operator", "viewer"]

  // Fetch tenants (for superadmin)
  useEffect(() => {
    if (isSuperAdmin) {
      fetchTenants()
    }
  }, [isSuperAdmin])

  // Fetch users
  useEffect(() => {
    if (canManageUsers) {
      fetchUsers()
    }
  }, [canManageUsers, selectedTenant])
  
  // Set default tenant for create form
  useEffect(() => {
    if (!isSuperAdmin && tenantUser) {
      setCreateFormData(prev => ({ ...prev, tenant_id: tenantUser.tenant_id }))
    }
  }, [isSuperAdmin, tenantUser])

  const fetchTenants = async () => {
    try {
      const response = await fetch(`${API_URL}/api/tenants`)
      if (response.ok) {
        const data = await response.json()
        setTenants(data)
      }
    } catch (error) {
      console.error("Error fetching tenants:", error)
    }
  }

  const fetchUsers = async () => {
    try {
      setLoading(true)
      let url = `${API_URL}/api/users`
      
      // Superadmin can filter by tenant
      if (isSuperAdmin && selectedTenant) {
        url += `?tenant_id=${selectedTenant}`
      }
      
      const response = await fetch(url, {
        headers: {
          "X-User-Id": tenantUser?.id || "",
        },
      })
      
      if (response.ok) {
        const data = await response.json()
        setUsers(data)
      }
    } catch (error) {
      console.error("Error fetching users:", error)
    } finally {
      setLoading(false)
    }
  }  
  const handleCreateUser = async () => {
    // Validations
    if (!createFormData.email || !createFormData.password) {
      alert("Email y contraseña son requeridos")
      return
    }
    
    if (!createFormData.tenant_id) {
      alert("Debe seleccionar un tenant")
      return
    }

    try {
      const response = await fetch(`${API_URL}/api/users`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-User-Id": tenantUser?.id || "",
        },
        body: JSON.stringify(createFormData),
      })

      if (response.ok) {
        await fetchUsers()
        setCreateDialogOpen(false)
        // Reset form
        setCreateFormData({
          email: "",
          name: "",
          password: "",
          role: "viewer",
          tenant_id: isSuperAdmin ? 0 : (tenantUser?.tenant_id || 0),
          all_locations_access: false,
        })
      } else {
        const error = await response.json()
        alert(error.detail || "Error al crear usuario")
      }
    } catch (error) {
      console.error("Error creating user:", error)
      alert("Error al crear usuario")
    }
  }
  const handleEdit = (user: User) => {
    setSelectedUser(user)
    setFormData({
      name: user.name || "",
      role: user.role,
      tenant_id: user.tenant_id,
      all_locations_access: false, // Will be loaded from detail
      is_active: user.is_active,
    })
    setEditDialogOpen(true)
  }

  const handleDelete = (user: User) => {
    setSelectedUser(user)
    setDeleteDialogOpen(true)
  }

  const handleUpdateUser = async () => {
    if (!selectedUser) return

    try {
      const response = await fetch(`${API_URL}/api/users/${selectedUser.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "X-User-Id": tenantUser?.id || "",
        },
        body: JSON.stringify(formData),
      })

      if (response.ok) {
        await fetchUsers()
        setEditDialogOpen(false)
        setSelectedUser(null)
      } else {
        const error = await response.json()
        alert(error.detail || "Error al actualizar usuario")
      }
    } catch (error) {
      console.error("Error updating user:", error)
      alert("Error al actualizar usuario")
    }
  }

  const handleDeleteUser = async () => {
    if (!selectedUser) return

    try {
      const response = await fetch(`${API_URL}/api/users/${selectedUser.id}`, {
        method: "DELETE",
        headers: {
          "X-User-Id": tenantUser?.id || "",
        },
      })

      if (response.ok) {
        await fetchUsers()
        setDeleteDialogOpen(false)
        setSelectedUser(null)
      } else {
        const error = await response.json()
        alert(error.detail || "Error al eliminar usuario")
      }
    } catch (error) {
      console.error("Error deleting user:", error)
      alert("Error al eliminar usuario")
    }
  }

  const getRoleBadge = (role: string) => {
    const config = ROLE_CONFIG[role as keyof typeof ROLE_CONFIG]
    if (!config) return <Badge variant="outline">{role}</Badge>

    const Icon = config.icon
    return (
      <Badge className={config.color} variant="outline">
        <Icon className="mr-1 h-3 w-3" />
        {config.label}
      </Badge>
    )
  }

  if (tenantLoading) {
    return <div className="flex items-center justify-center p-8">Cargando...</div>
  }

  if (!canManageUsers) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-center">
        <Shield className="h-12 w-12 text-gray-400 mb-4" />
        <h3 className="text-lg font-semibold mb-2">Acceso Restringido</h3>
        <p className="text-gray-600">
          Solo los administradores pueden gestionar usuarios.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6 mx-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Gestión de Usuarios</h2>
          <p className="text-muted-foreground">
            {isSuperAdmin 
              ? "Gestiona usuarios de todos los tenants" 
              : `Gestiona usuarios de ${tenantUser?.tenant_name}`
            }
          </p>
        </div>
        
        <div className="flex items-center gap-4">
          {/* Tenant filter (superadmin only) */}
          {isSuperAdmin && tenants.length > 0 && (
            <Select
              value={selectedTenant?.toString() || "all"}
              onValueChange={(value) => setSelectedTenant(value === "all" ? null : Number(value))}
            >
              <SelectTrigger className="w-50">
                <SelectValue placeholder="Todos los tenants" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos los tenants</SelectItem>
                {tenants.map((tenant) => (
                  <SelectItem key={tenant.id} value={tenant.id.toString()}>
                    {tenant.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          <Button onClick={() => setCreateDialogOpen(true)}>
            <UserPlus className="mr-2 h-4 w-4" />
            Crear Usuario
          </Button>
        </div>
      </div>

      {/* Users table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Usuario</TableHead>
              {isSuperAdmin && <TableHead>Tenant</TableHead>}
              <TableHead>Rol</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Creado</TableHead>
              <TableHead className="w-12.5"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={isSuperAdmin ? 6 : 5} className="text-center py-8">
                  Cargando usuarios...
                </TableCell>
              </TableRow>
            ) : users.length === 0 ? (
              <TableRow>
                <TableCell colSpan={isSuperAdmin ? 6 : 5} className="text-center py-8">
                  No hay usuarios
                </TableCell>
              </TableRow>
            ) : (
              users.map((user) => (
                <TableRow key={user.id}>
                  <TableCell>
                    <div>
                      <div className="font-medium">{user.name || "Sin nombre"}</div>
                      <div className="text-sm text-gray-500">{user.email}</div>
                    </div>
                  </TableCell>
                  
                  {isSuperAdmin && (
                    <TableCell>
                      <span className="text-sm font-medium">{user.tenant_name}</span>
                    </TableCell>
                  )}
                  
                  <TableCell>{getRoleBadge(user.role)}</TableCell>
                  
                  <TableCell>
                    {user.is_active ? (
                      <Badge variant="outline" className="text-green-600 bg-green-50">
                        Activo
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-red-600 bg-red-50">
                        Inactivo
                      </Badge>
                    )}
                  </TableCell>
                  
                  <TableCell>
                    {new Date(user.created_at).toLocaleDateString()}
                  </TableCell>
                  
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon">
                          <MoreVertical className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuLabel>Acciones</DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onClick={() => handleEdit(user)}>
                          <Pencil className="mr-2 h-4 w-4" />
                          Editar
                        </DropdownMenuItem>
                        <DropdownMenuItem 
                          onClick={() => handleDelete(user)}
                          className="text-red-600"
                          disabled={user.id === tenantUser?.id}
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Eliminar
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Editar Usuario</DialogTitle>
            <DialogDescription>
              Modifica el rol y permisos del usuario
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Email</Label>
              <Input value={selectedUser?.email || ""} disabled />
            </div>

            <div className="space-y-2">
              <Label htmlFor="name">Nombre</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Nombre del usuario"
              />
            </div>

            {isSuperAdmin && (
              <div className="space-y-2">
                <Label htmlFor="tenant">Tenant</Label>
                <Select
                  value={formData.tenant_id.toString()}
                  onValueChange={(value) => setFormData({ ...formData, tenant_id: parseInt(value) })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {tenants.map((tenant) => (
                      <SelectItem key={tenant.id} value={tenant.id.toString()}>
                        {tenant.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-gray-500">
                  Cambiar el tenant moverá al usuario a otra organización
                </p>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="role">Rol</Label>
              <Select
                value={formData.role}
                onValueChange={(value: any) => setFormData({ ...formData, role: value })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {availableRoles.map((role) => {
                    const config = ROLE_CONFIG[role as keyof typeof ROLE_CONFIG]
                    return (
                      <SelectItem key={role} value={role}>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{config.label}</span>
                          <span className="text-xs text-gray-500">- {config.description}</span>
                        </div>
                      </SelectItem>
                    )
                  })}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label>Acceso a todas las ubicaciones</Label>
                <p className="text-sm text-gray-500">
                  El usuario puede ver todas las ubicaciones del tenant
                </p>
              </div>
              <Switch
                checked={formData.all_locations_access}
                onCheckedChange={(checked) =>
                  setFormData({ ...formData, all_locations_access: checked })
                }
              />
            </div>

            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label>Usuario activo</Label>
                <p className="text-sm text-gray-500">
                  Los usuarios inactivos no pueden acceder al sistema
                </p>
              </div>
              <Switch
                checked={formData.is_active}
                onCheckedChange={(checked) =>
                  setFormData({ ...formData, is_active: checked })
                }
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={handleUpdateUser}>
              Guardar Cambios
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Eliminar Usuario</DialogTitle>
            <DialogDescription>
              ¿Estás seguro de que deseas eliminar este usuario del tenant?
            </DialogDescription>
          </DialogHeader>

          <div className="py-4">
            <p className="text-sm">
              Usuario: <strong>{selectedUser?.name || selectedUser?.email}</strong>
            </p>
            <p className="text-sm text-red-600 mt-2">
              Esta acción eliminará el usuario del tenant pero no borrará su cuenta de autenticación.
            </p>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Cancelar
            </Button>
            <Button variant="destructive" onClick={handleDeleteUser}>
              Eliminar Usuario
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      
      {/* Create User Dialog */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Crear Nuevo Usuario</DialogTitle>
            <DialogDescription>
              Crea un nuevo usuario y asígnalo a un tenant
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="create-email">Email *</Label>
              <Input
                id="create-email"
                type="email"
                placeholder="usuario@ejemplo.com"
                value={createFormData.email}
                onChange={(e) =>
                  setCreateFormData({ ...createFormData, email: e.target.value })
                }
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="create-name">Nombre</Label>
              <Input
                id="create-name"
                placeholder="Nombre completo"
                value={createFormData.name}
                onChange={(e) =>
                  setCreateFormData({ ...createFormData, name: e.target.value })
                }
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="create-password">Contraseña *</Label>
              <Input
                id="create-password"
                type="password"
                placeholder="Contraseña segura"
                value={createFormData.password}
                onChange={(e) =>
                  setCreateFormData({ ...createFormData, password: e.target.value })
                }
              />
            </div>

            {/* Tenant selector (only for superadmin) */}
            {isSuperAdmin && (
              <div className="grid gap-2">
                <Label htmlFor="create-tenant">Tenant *</Label>
                <Select
                  value={createFormData.tenant_id.toString()}
                  onValueChange={(value) =>
                    setCreateFormData({ ...createFormData, tenant_id: Number(value) })
                  }
                >
                  <SelectTrigger id="create-tenant">
                    <SelectValue placeholder="Seleccionar tenant" />
                  </SelectTrigger>
                  <SelectContent>
                    {tenants.map((tenant) => (
                      <SelectItem key={tenant.id} value={tenant.id.toString()}>
                        {tenant.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="grid gap-2">
              <Label htmlFor="create-role">Rol</Label>
              <Select
                value={createFormData.role}
                onValueChange={(value: any) =>
                  setCreateFormData({ ...createFormData, role: value })
                }
              >
                <SelectTrigger id="create-role">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {availableRoles.map((role) => {
                    const config = ROLE_CONFIG[role as keyof typeof ROLE_CONFIG]
                    const Icon = config.icon
                    return (
                      <SelectItem key={role} value={role}>
                        <div className="flex items-center">
                          <Icon className="mr-2 h-4 w-4" />
                          {config.label}
                        </div>
                      </SelectItem>
                    )
                  })}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center justify-between rounded-lg border p-3">
              <div className="space-y-0.5">
                <div className="text-sm font-medium">Acceso a todas las ubicaciones</div>
                <p className="text-sm text-gray-500">
                  El usuario puede ver todas las ubicaciones del tenant
                </p>
              </div>
              <Switch
                checked={createFormData.all_locations_access}
                onCheckedChange={(checked) =>
                  setCreateFormData({ ...createFormData, all_locations_access: checked })
                }
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={handleCreateUser}>
              Crear Usuario
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
