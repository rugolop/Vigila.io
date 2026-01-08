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
  MapPin, 
  Plus, 
  Edit, 
  Trash2, 
  Camera, 
  Loader2,
  Building2,
  Globe
} from "lucide-react"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"

interface Location {
  id: number
  tenant_id: number
  name: string
  address: string | null
  city: string | null
  country: string | null
  latitude: string | null
  longitude: string | null
  timezone: string
  is_active: boolean
  created_at: string
  updated_at: string
  cameras_count: number
}

interface Tenant {
  id: number
  name: string
  slug: string
}

interface LocationFormData {
  name: string
  address: string
  city: string
  country: string
  timezone: string
  tenant_id: number
}

export function LocationManager() {
  const [locations, setLocations] = useState<Location[]>([])
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [editingLocation, setEditingLocation] = useState<Location | null>(null)
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [selectedTenant, setSelectedTenant] = useState<number | null>(null)
  const [formData, setFormData] = useState<LocationFormData>({
    name: "",
    address: "",
    city: "",
    country: "",
    timezone: "UTC",
    tenant_id: 0,
  })

  const fetchTenants = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/tenants`)
      if (response.ok) {
        const data = await response.json()
        setTenants(data)
        // Auto-select first tenant if only one exists
        if (data.length === 1 && !selectedTenant) {
          setSelectedTenant(data[0].id)
        }
      }
    } catch (error) {
      console.error("Error fetching tenants:", error)
    }
  }, [selectedTenant])

  const fetchLocations = useCallback(async () => {
    try {
      setLoading(true)
      let url = `${API_URL}/api/locations`
      if (selectedTenant) {
        url += `?tenant_id=${selectedTenant}`
      }
      const response = await fetch(url)
      if (response.ok) {
        const data = await response.json()
        setLocations(data)
      }
    } catch (error) {
      console.error("Error fetching locations:", error)
    } finally {
      setLoading(false)
    }
  }, [selectedTenant])

  useEffect(() => {
    fetchTenants()
  }, [fetchTenants])

  useEffect(() => {
    fetchLocations()
  }, [fetchLocations])

  const handleCreate = async () => {
    if (!formData.name || !formData.tenant_id) return

    setCreating(true)
    try {
      const response = await fetch(`${API_URL}/api/locations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      })

      if (response.ok) {
        await fetchLocations()
        setIsDialogOpen(false)
        resetForm()
      } else {
        const error = await response.json()
        alert(error.detail || "Error al crear ubicación")
      }
    } catch (error) {
      console.error("Error creating location:", error)
    } finally {
      setCreating(false)
    }
  }

  const handleUpdate = async () => {
    if (!editingLocation) return

    setCreating(true)
    try {
      const response = await fetch(`${API_URL}/api/locations/${editingLocation.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: formData.name,
          address: formData.address,
          city: formData.city,
          country: formData.country,
          timezone: formData.timezone,
        }),
      })

      if (response.ok) {
        await fetchLocations()
        setIsDialogOpen(false)
        setEditingLocation(null)
        resetForm()
      } else {
        const error = await response.json()
        alert(error.detail || "Error al actualizar ubicación")
      }
    } catch (error) {
      console.error("Error updating location:", error)
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (location: Location) => {
    if (location.cameras_count > 0) {
      alert(`No se puede eliminar una ubicación con ${location.cameras_count} cámaras. Mueve las cámaras primero.`)
      return
    }

    if (!confirm(`¿Eliminar la ubicación "${location.name}"?`)) return

    try {
      const response = await fetch(`${API_URL}/api/locations/${location.id}`, {
        method: "DELETE",
      })

      if (response.ok) {
        await fetchLocations()
      } else {
        const error = await response.json()
        alert(error.detail || "Error al eliminar ubicación")
      }
    } catch (error) {
      console.error("Error deleting location:", error)
    }
  }

  const openEditDialog = (location: Location) => {
    setEditingLocation(location)
    setFormData({
      name: location.name,
      address: location.address || "",
      city: location.city || "",
      country: location.country || "",
      timezone: location.timezone,
      tenant_id: location.tenant_id,
    })
    setIsDialogOpen(true)
  }

  const openCreateDialog = () => {
    setEditingLocation(null)
    resetForm()
    if (selectedTenant) {
      setFormData(prev => ({ ...prev, tenant_id: selectedTenant }))
    }
    setIsDialogOpen(true)
  }

  const resetForm = () => {
    setFormData({
      name: "",
      address: "",
      city: "",
      country: "",
      timezone: "UTC",
      tenant_id: selectedTenant || 0,
    })
  }

  const timezones = [
    "UTC",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Mexico_City",
    "America/Bogota",
    "America/Lima",
    "America/Santiago",
    "America/Buenos_Aires",
    "America/Sao_Paulo",
    "Europe/London",
    "Europe/Paris",
    "Europe/Madrid",
    "Europe/Berlin",
    "Europe/Rome",
    "Asia/Tokyo",
    "Asia/Shanghai",
    "Asia/Singapore",
    "Asia/Dubai",
    "Australia/Sydney",
  ]

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <MapPin className="h-5 w-5" />
              Ubicaciones
            </CardTitle>
            <CardDescription>
              Gestiona las ubicaciones físicas y asigna cámaras a cada una
            </CardDescription>
          </div>
          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button onClick={openCreateDialog}>
                <Plus className="h-4 w-4 mr-2" />
                Nueva Ubicación
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[500px]">
              <DialogHeader>
                <DialogTitle>
                  {editingLocation ? "Editar Ubicación" : "Nueva Ubicación"}
                </DialogTitle>
                <DialogDescription>
                  {editingLocation
                    ? "Modifica los datos de la ubicación"
                    : "Añade una nueva ubicación física para organizar tus cámaras"}
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                {!editingLocation && (
                  <div className="grid gap-2">
                    <Label htmlFor="tenant">Organización</Label>
                    <select
                      id="tenant"
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                      value={formData.tenant_id}
                      onChange={(e) => setFormData({ ...formData, tenant_id: Number(e.target.value) })}
                    >
                      <option value={0}>Selecciona una organización</option>
                      {tenants.map((tenant) => (
                        <option key={tenant.id} value={tenant.id}>
                          {tenant.name}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                <div className="grid gap-2">
                  <Label htmlFor="name">Nombre *</Label>
                  <Input
                    id="name"
                    placeholder="Ej: Oficina Central"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="address">Dirección</Label>
                  <Input
                    id="address"
                    placeholder="Ej: Calle Principal 123"
                    value={formData.address}
                    onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <Label htmlFor="city">Ciudad</Label>
                    <Input
                      id="city"
                      placeholder="Ej: Madrid"
                      value={formData.city}
                      onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="country">País</Label>
                    <Input
                      id="country"
                      placeholder="Ej: España"
                      value={formData.country}
                      onChange={(e) => setFormData({ ...formData, country: e.target.value })}
                    />
                  </div>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="timezone">Zona Horaria</Label>
                  <select
                    id="timezone"
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={formData.timezone}
                    onChange={(e) => setFormData({ ...formData, timezone: e.target.value })}
                  >
                    {timezones.map((tz) => (
                      <option key={tz} value={tz}>
                        {tz}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
                  Cancelar
                </Button>
                <Button
                  onClick={editingLocation ? handleUpdate : handleCreate}
                  disabled={creating || !formData.name || (!editingLocation && !formData.tenant_id)}
                >
                  {creating ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      {editingLocation ? "Guardando..." : "Creando..."}
                    </>
                  ) : editingLocation ? (
                    "Guardar cambios"
                  ) : (
                    "Crear ubicación"
                  )}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </CardHeader>
      <CardContent>
        {/* Tenant filter */}
        {tenants.length > 1 && (
          <div className="flex items-center gap-4 mb-4">
            <Label>Filtrar por organización:</Label>
            <select
              className="flex h-9 rounded-md border border-input bg-background px-3 py-1 text-sm"
              value={selectedTenant || ""}
              onChange={(e) => setSelectedTenant(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">Todas las organizaciones</option>
              {tenants.map((tenant) => (
                <option key={tenant.id} value={tenant.id}>
                  {tenant.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {loading ? (
          <div className="space-y-3">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : locations.length === 0 ? (
          <div className="text-center py-10 text-muted-foreground">
            <MapPin className="h-10 w-10 mx-auto mb-3 opacity-50" />
            <p>No hay ubicaciones configuradas</p>
            <p className="text-sm">Crea una ubicación para organizar tus cámaras</p>
          </div>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nombre</TableHead>
                  <TableHead>Dirección</TableHead>
                  <TableHead>Zona Horaria</TableHead>
                  <TableHead className="text-center">Cámaras</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead className="text-right">Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {locations.map((location) => (
                  <TableRow key={location.id}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        <Building2 className="h-4 w-4 text-muted-foreground" />
                        {location.name}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm">
                        {location.address && <div>{location.address}</div>}
                        <div className="text-muted-foreground">
                          {[location.city, location.country].filter(Boolean).join(", ") || "-"}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1 text-sm">
                        <Globe className="h-3 w-3" />
                        {location.timezone}
                      </div>
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge variant="secondary" className="gap-1">
                        <Camera className="h-3 w-3" />
                        {location.cameras_count}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={location.is_active ? "default" : "secondary"}>
                        {location.is_active ? "Activa" : "Inactiva"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => openEditDialog(location)}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDelete(location)}
                          disabled={location.cameras_count > 0}
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
