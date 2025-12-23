"use client"

import { useState, useEffect, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { 
  Dialog, 
  DialogContent, 
  DialogDescription, 
  DialogFooter, 
  DialogHeader, 
  DialogTitle,
  DialogTrigger 
} from "@/components/ui/dialog"
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { 
  Building, 
  Plus, 
  Edit, 
  Trash2, 
  Users, 
  MapPin, 
  Camera,
  Loader2,
  Mail,
  Phone,
  HardDrive
} from "lucide-react"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

interface Tenant {
  id: number
  name: string
  slug: string
  status: string
  contact_email: string | null
  contact_phone: string | null
  max_cameras: number
  max_users: number
  max_locations: number
  storage_quota_gb: number
  created_at: string
  updated_at: string
  cameras_count: number
  users_count: number
  locations_count: number
}

interface TenantFormData {
  name: string
  slug: string
  contact_email: string
  contact_phone: string
  max_cameras: number
  max_users: number
  max_locations: number
  storage_quota_gb: number
}

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .replace(/[\s_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
}

export function TenantManager() {
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [editingTenant, setEditingTenant] = useState<Tenant | null>(null)
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [formData, setFormData] = useState<TenantFormData>({
    name: "",
    slug: "",
    contact_email: "",
    contact_phone: "",
    max_cameras: 10,
    max_users: 5,
    max_locations: 3,
    storage_quota_gb: 100,
  })

  const fetchTenants = useCallback(async () => {
    try {
      setLoading(true)
      const response = await fetch(`${API_URL}/api/tenants`)
      if (response.ok) {
        const data = await response.json()
        setTenants(data)
      }
    } catch (error) {
      console.error("Error fetching tenants:", error)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchTenants()
  }, [fetchTenants])

  const handleNameChange = (name: string) => {
    setFormData({
      ...formData,
      name,
      slug: editingTenant ? formData.slug : slugify(name),
    })
  }

  const handleCreate = async () => {
    if (!formData.name || !formData.slug) return

    setCreating(true)
    try {
      const response = await fetch(`${API_URL}/api/tenants`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      })

      if (response.ok) {
        await fetchTenants()
        setIsDialogOpen(false)
        resetForm()
      } else {
        const error = await response.json()
        alert(error.detail || "Error al crear organización")
      }
    } catch (error) {
      console.error("Error creating tenant:", error)
    } finally {
      setCreating(false)
    }
  }

  const handleUpdate = async () => {
    if (!editingTenant) return

    setCreating(true)
    try {
      const response = await fetch(`${API_URL}/api/tenants/${editingTenant.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: formData.name,
          contact_email: formData.contact_email || null,
          contact_phone: formData.contact_phone || null,
          max_cameras: formData.max_cameras,
          max_users: formData.max_users,
          max_locations: formData.max_locations,
          storage_quota_gb: formData.storage_quota_gb,
        }),
      })

      if (response.ok) {
        await fetchTenants()
        setIsDialogOpen(false)
        setEditingTenant(null)
        resetForm()
      } else {
        const error = await response.json()
        alert(error.detail || "Error al actualizar organización")
      }
    } catch (error) {
      console.error("Error updating tenant:", error)
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (tenant: Tenant) => {
    if (tenant.slug === "default") {
      alert("No se puede eliminar la organización por defecto")
      return
    }

    if (tenant.cameras_count > 0 || tenant.users_count > 0 || tenant.locations_count > 0) {
      alert("No se puede eliminar una organización con datos asociados")
      return
    }

    if (!confirm(`¿Eliminar la organización "${tenant.name}"?`)) return

    try {
      const response = await fetch(`${API_URL}/api/tenants/${tenant.id}`, {
        method: "DELETE",
      })

      if (response.ok) {
        await fetchTenants()
      } else {
        const error = await response.json()
        alert(error.detail || "Error al eliminar organización")
      }
    } catch (error) {
      console.error("Error deleting tenant:", error)
    }
  }

  const openEditDialog = (tenant: Tenant) => {
    setEditingTenant(tenant)
    setFormData({
      name: tenant.name,
      slug: tenant.slug,
      contact_email: tenant.contact_email || "",
      contact_phone: tenant.contact_phone || "",
      max_cameras: tenant.max_cameras,
      max_users: tenant.max_users,
      max_locations: tenant.max_locations,
      storage_quota_gb: tenant.storage_quota_gb,
    })
    setIsDialogOpen(true)
  }

  const openCreateDialog = () => {
    setEditingTenant(null)
    resetForm()
    setIsDialogOpen(true)
  }

  const resetForm = () => {
    setFormData({
      name: "",
      slug: "",
      contact_email: "",
      contact_phone: "",
      max_cameras: 10,
      max_users: 5,
      max_locations: 3,
      storage_quota_gb: 100,
    })
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "active":
        return <Badge variant="default">Activo</Badge>
      case "suspended":
        return <Badge variant="destructive">Suspendido</Badge>
      case "trial":
        return <Badge variant="secondary">Prueba</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Building className="h-5 w-5" />
              Organizaciones
            </CardTitle>
            <CardDescription>
              Gestiona las organizaciones (clientes/tenants) del sistema
            </CardDescription>
          </div>
          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button onClick={openCreateDialog}>
                <Plus className="h-4 w-4 mr-2" />
                Nueva Organización
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[550px]">
              <DialogHeader>
                <DialogTitle>
                  {editingTenant ? "Editar Organización" : "Nueva Organización"}
                </DialogTitle>
                <DialogDescription>
                  {editingTenant
                    ? "Modifica los datos de la organización"
                    : "Crea una nueva organización para agrupar usuarios, ubicaciones y cámaras"}
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                <div className="grid gap-2">
                  <Label htmlFor="name">Nombre *</Label>
                  <Input
                    id="name"
                    placeholder="Ej: Empresa ABC"
                    value={formData.name}
                    onChange={(e) => handleNameChange(e.target.value)}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="slug">
                    Identificador (slug) *
                    {editingTenant && (
                      <span className="text-muted-foreground ml-2 text-xs">(no editable)</span>
                    )}
                  </Label>
                  <Input
                    id="slug"
                    placeholder="empresa-abc"
                    value={formData.slug}
                    onChange={(e) => setFormData({ ...formData, slug: slugify(e.target.value) })}
                    disabled={!!editingTenant}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <Label htmlFor="contact_email">Email de contacto</Label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                      <Input
                        id="contact_email"
                        type="email"
                        className="pl-9"
                        placeholder="contacto@empresa.com"
                        value={formData.contact_email}
                        onChange={(e) => setFormData({ ...formData, contact_email: e.target.value })}
                      />
                    </div>
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="contact_phone">Teléfono</Label>
                    <div className="relative">
                      <Phone className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                      <Input
                        id="contact_phone"
                        className="pl-9"
                        placeholder="+34 600 000 000"
                        value={formData.contact_phone}
                        onChange={(e) => setFormData({ ...formData, contact_phone: e.target.value })}
                      />
                    </div>
                  </div>
                </div>
                
                <div className="border-t pt-4 mt-2">
                  <h4 className="font-medium mb-3">Límites del plan</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="grid gap-2">
                      <Label htmlFor="max_cameras" className="flex items-center gap-1">
                        <Camera className="h-3 w-3" />
                        Máx. Cámaras
                      </Label>
                      <Input
                        id="max_cameras"
                        type="number"
                        min={1}
                        value={formData.max_cameras}
                        onChange={(e) => setFormData({ ...formData, max_cameras: Number(e.target.value) })}
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="max_users" className="flex items-center gap-1">
                        <Users className="h-3 w-3" />
                        Máx. Usuarios
                      </Label>
                      <Input
                        id="max_users"
                        type="number"
                        min={1}
                        value={formData.max_users}
                        onChange={(e) => setFormData({ ...formData, max_users: Number(e.target.value) })}
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="max_locations" className="flex items-center gap-1">
                        <MapPin className="h-3 w-3" />
                        Máx. Ubicaciones
                      </Label>
                      <Input
                        id="max_locations"
                        type="number"
                        min={1}
                        value={formData.max_locations}
                        onChange={(e) => setFormData({ ...formData, max_locations: Number(e.target.value) })}
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="storage_quota_gb" className="flex items-center gap-1">
                        <HardDrive className="h-3 w-3" />
                        Almacenamiento (GB)
                      </Label>
                      <Input
                        id="storage_quota_gb"
                        type="number"
                        min={1}
                        value={formData.storage_quota_gb}
                        onChange={(e) => setFormData({ ...formData, storage_quota_gb: Number(e.target.value) })}
                      />
                    </div>
                  </div>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
                  Cancelar
                </Button>
                <Button
                  onClick={editingTenant ? handleUpdate : handleCreate}
                  disabled={creating || !formData.name || !formData.slug}
                >
                  {creating ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      {editingTenant ? "Guardando..." : "Creando..."}
                    </>
                  ) : editingTenant ? (
                    "Guardar cambios"
                  ) : (
                    "Crear organización"
                  )}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-3">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : tenants.length === 0 ? (
          <div className="text-center py-10 text-muted-foreground">
            <Building className="h-10 w-10 mx-auto mb-3 opacity-50" />
            <p>No hay organizaciones configuradas</p>
            <p className="text-sm">Crea una organización para comenzar</p>
          </div>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Organización</TableHead>
                  <TableHead>Contacto</TableHead>
                  <TableHead className="text-center">Ubicaciones</TableHead>
                  <TableHead className="text-center">Cámaras</TableHead>
                  <TableHead className="text-center">Usuarios</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead className="text-right">Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tenants.map((tenant) => (
                  <TableRow key={tenant.id}>
                    <TableCell>
                      <div>
                        <div className="font-medium">{tenant.name}</div>
                        <div className="text-sm text-muted-foreground">/{tenant.slug}</div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm">
                        {tenant.contact_email && (
                          <div className="flex items-center gap-1">
                            <Mail className="h-3 w-3" />
                            {tenant.contact_email}
                          </div>
                        )}
                        {tenant.contact_phone && (
                          <div className="flex items-center gap-1 text-muted-foreground">
                            <Phone className="h-3 w-3" />
                            {tenant.contact_phone}
                          </div>
                        )}
                        {!tenant.contact_email && !tenant.contact_phone && "-"}
                      </div>
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge variant="outline" className="gap-1">
                        <MapPin className="h-3 w-3" />
                        {tenant.locations_count}/{tenant.max_locations}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge variant="outline" className="gap-1">
                        <Camera className="h-3 w-3" />
                        {tenant.cameras_count}/{tenant.max_cameras}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge variant="outline" className="gap-1">
                        <Users className="h-3 w-3" />
                        {tenant.users_count}/{tenant.max_users}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {getStatusBadge(tenant.status)}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => openEditDialog(tenant)}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDelete(tenant)}
                          disabled={
                            tenant.slug === "default" ||
                            tenant.cameras_count > 0 ||
                            tenant.users_count > 0 ||
                            tenant.locations_count > 0
                          }
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
