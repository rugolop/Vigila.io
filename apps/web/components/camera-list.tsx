"use client"

import { useState, useEffect, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Video, VideoOff, Loader2 } from "lucide-react"

interface Camera {
  id: number
  name: string
  rtsp_url: string
  is_active: boolean
  is_recording?: boolean
  stream_mode?: string
  tenant_id?: number
  location_id?: number
  created_at: string
}

interface Tenant {
  id: number
  name: string
  slug: string
}

interface Location {
  id: number
  name: string
  tenant_id: number
}

interface ConnectionTestResult {
  success: boolean
  message: string
  video_info?: {
    codec: string
    width: number
    height: number
    framerate: string
  } | null
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"

export const CameraList = () => {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [newCameraName, setNewCameraName] = useState("")
  const [newCameraUrl, setNewCameraUrl] = useState("")
  const [loading, setLoading] = useState(false)
  
  // Tenant and Location state
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [locations, setLocations] = useState<Location[]>([])
  const [selectedTenantId, setSelectedTenantId] = useState("")
  const [selectedLocationId, setSelectedLocationId] = useState("")
  const [filteredLocations, setFilteredLocations] = useState<Location[]>([])
  
  // Edit state
  const [editingCamera, setEditingCamera] = useState<Camera | null>(null)
  const [editName, setEditName] = useState("")
  const [editUrl, setEditUrl] = useState("")
  const [editMode, setEditMode] = useState("")
  const [editTenantId, setEditTenantId] = useState("")
  const [editLocationId, setEditLocationId] = useState("")
  const [saving, setSaving] = useState(false)
  
  // Connection test state
  const [testingConnection, setTestingConnection] = useState(false)
  const [connectionResult, setConnectionResult] = useState<ConnectionTestResult | null>(null)
  
  // Recording toggle state
  const [togglingRecording, setTogglingRecording] = useState<number | null>(null)

  // Fetch tenants
  const fetchTenants = async () => {
    try {
      const response = await fetch(`${API_URL}/api/tenants`)
      if (response.ok) {
        const data = await response.json()
        setTenants(data)
      }
    } catch (error) {
      console.error("Failed to fetch tenants", error)
    }
  }

  // Fetch locations
  const fetchLocations = async () => {
    try {
      const response = await fetch(`${API_URL}/api/locations`)
      if (response.ok) {
        const data = await response.json()
        setLocations(data)
      }
    } catch (error) {
      console.error("Failed to fetch locations", error)
    }
  }

  // Filter locations by tenant
  useEffect(() => {
    if (selectedTenantId) {
      setFilteredLocations(locations.filter(loc => loc.tenant_id === parseInt(selectedTenantId)))
    } else {
      setFilteredLocations([])
    }
    setSelectedLocationId("")
  }, [selectedTenantId, locations])

  // Get filtered locations for edit dialog
  const getEditFilteredLocations = () => {
    if (editTenantId) {
      return locations.filter(loc => loc.tenant_id === parseInt(editTenantId))
    }
    return []
  }

  // Test RTSP connection
  const testRtspConnection = async (url: string) => {
    setTestingConnection(true)
    setConnectionResult(null)
    try {
      const response = await fetch(`${API_URL}/api/cameras/test-rtsp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rtsp_url: url }),
      })
      const data = await response.json()
      setConnectionResult(data)
    } catch (error) {
      setConnectionResult({ success: false, message: "Error de conexión al servidor" })
    } finally {
      setTestingConnection(false)
    }
  }

  const fetchCameras = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/cameras/`)
      if (response.ok) {
        const data = await response.json()
        setCameras(data)
      }
    } catch (error) {
      console.error("Failed to fetch cameras", error)
    }
  }, [])

  const handleAddCamera = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/api/cameras/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: newCameraName,
          rtsp_url: newCameraUrl,
          is_active: true,
          tenant_id: selectedTenantId ? parseInt(selectedTenantId) : null,
          location_id: selectedLocationId ? parseInt(selectedLocationId) : null,
        }),
      })

      if (response.ok) {
        setNewCameraName("")
        setNewCameraUrl("")
        setSelectedTenantId("")
        setSelectedLocationId("")
        setConnectionResult(null)
        fetchCameras()
      } else {
        const error = await response.json()
        alert(error.detail || "Error al agregar la cámara")
      }
    } catch (error) {
      console.error("Failed to add camera", error)
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteCamera = async (cameraId: number) => {
    if (!confirm("¿Estás seguro de que quieres eliminar esta cámara?")) {
      return
    }

    try {
      const response = await fetch(`${API_URL}/api/cameras/${cameraId}`, {
        method: "DELETE",
      })

      if (response.ok) {
        fetchCameras()
      }
    } catch (error) {
      console.error("Failed to delete camera", error)
    }
  }
  
  const handleToggleRecording = async (camera: Camera) => {
    setTogglingRecording(camera.id)
    try {
      const response = await fetch(`${API_URL}/api/cameras/${camera.id}/recording/toggle`, {
        method: "POST",
      })
      
      if (response.ok) {
        // Update local state immediately for better UX
        setCameras(prev => prev.map(c => 
          c.id === camera.id 
            ? { ...c, is_recording: !c.is_recording } 
            : c
        ))
      } else {
        const error = await response.json()
        alert(error.detail || "Error al cambiar estado de grabación")
      }
    } catch (error) {
      console.error("Failed to toggle recording", error)
      alert("Error de conexión")
    } finally {
      setTogglingRecording(null)
    }
  }

  // Open edit dialog
  const openEditDialog = (camera: Camera) => {
    setEditingCamera(camera)
    setEditName(camera.name)
    setEditUrl(camera.rtsp_url)
    setEditMode(camera.stream_mode || "auto")
    setEditTenantId(camera.tenant_id?.toString() || "")
    setEditLocationId(camera.location_id?.toString() || "")
    setConnectionResult(null)
  }

  // Update camera
  const handleUpdateCamera = async () => {
    if (!editingCamera) return
    
    setSaving(true)
    try {
      const response = await fetch(`${API_URL}/api/cameras/${editingCamera.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: editName,
          rtsp_url: editUrl,
          stream_mode: editMode,
          tenant_id: editTenantId ? parseInt(editTenantId) : null,
          location_id: editLocationId ? parseInt(editLocationId) : null,
        }),
      })

      if (response.ok) {
        fetchCameras()
        setEditingCamera(null)
        setConnectionResult(null)
      } else {
        const error = await response.json()
        alert(error.detail || "Error al actualizar la cámara")
      }
    } catch (error) {
      console.error("Failed to update camera", error)
    } finally {
      setSaving(false)
    }
  }

  // Get tenant/location names
  const getTenantName = (tenantId?: number) => {
    if (!tenantId) return "-"
    const tenant = tenants.find(t => t.id === tenantId)
    return tenant?.name || "-"
  }

  const getLocationName = (locationId?: number) => {
    if (!locationId) return "-"
    const location = locations.find(l => l.id === locationId)
    return location?.name || "-"
  }

  useEffect(() => {
    fetchCameras()
    fetchTenants()
    fetchLocations()
  }, [fetchCameras])

  return (
    <div className="grid gap-6">
      {/* Manual Add Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 5v14M5 12h14"/>
            </svg>
            Añadir Cámara Manualmente
          </CardTitle>
          <CardDescription>
            Ingresa la información de tu cámara IP manualmente
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAddCamera} className="grid gap-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="name">Nombre de la Cámara</Label>
                <Input
                  id="name"
                  placeholder="ej. Puerta Principal"
                  value={newCameraName}
                  onChange={(e) => setNewCameraName(e.target.value)}
                  required
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="url">URL RTSP</Label>
                <Input
                  id="url"
                  placeholder="rtsp://..."
                  value={newCameraUrl}
                  onChange={(e) => setNewCameraUrl(e.target.value)}
                  required
                />
              </div>
            </div>
            
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label>Organización (Tenant)</Label>
                <Select value={selectedTenantId} onValueChange={setSelectedTenantId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Seleccionar organización" />
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
              <div className="grid gap-2">
                <Label>Ubicación</Label>
                <Select 
                  value={selectedLocationId} 
                  onValueChange={setSelectedLocationId}
                  disabled={!selectedTenantId}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={selectedTenantId ? "Seleccionar ubicación" : "Primero seleccione organización"} />
                  </SelectTrigger>
                  <SelectContent>
                    {filteredLocations.map((location) => (
                      <SelectItem key={location.id} value={location.id.toString()}>
                        {location.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            
            <div className="flex gap-2 items-center flex-wrap">
              <Button 
                type="button" 
                variant="outline"
                disabled={!newCameraUrl || testingConnection}
                onClick={() => testRtspConnection(newCameraUrl)}
              >
                {testingConnection ? "Probando..." : "Probar Conexión"}
              </Button>
              
              {connectionResult && (
                <span className={`text-sm ${connectionResult.success ? "text-green-600" : "text-red-600"}`}>
                  {connectionResult.success ? "✓ " : "✗ "}
                  {connectionResult.message}
                  {connectionResult.video_info && (
                    <span className="ml-2 text-gray-500">
                      ({connectionResult.video_info.codec} {connectionResult.video_info.width}x{connectionResult.video_info.height})
                    </span>
                  )}
                </span>
              )}
            </div>
            
            <div className="flex gap-2">
              <Button type="submit" disabled={loading}>
                {loading ? "Añadiendo..." : "Añadir Cámara"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Connected Cameras */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
              <circle cx="12" cy="13" r="4"/>
            </svg>
            Cámaras Conectadas
          </CardTitle>
          <CardDescription>
            Lista de todas las cámaras configuradas en el sistema
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Nombre</TableHead>
                <TableHead>Organización</TableHead>
                <TableHead>Ubicación</TableHead>
                <TableHead>URL RTSP</TableHead>
                <TableHead>Modo</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Grabando</TableHead>
                <TableHead>Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {cameras.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={9} className="text-center text-muted-foreground py-8">
                    No hay cámaras configuradas. Añade una cámara manualmente o usa el descubrimiento de red.
                  </TableCell>
                </TableRow>
              ) : (
                cameras.map((camera) => (
                  <TableRow key={camera.id}>
                    <TableCell className="font-mono">{camera.id}</TableCell>
                    <TableCell className="font-medium">{camera.name}</TableCell>
                    <TableCell>{getTenantName(camera.tenant_id)}</TableCell>
                    <TableCell>{getLocationName(camera.location_id)}</TableCell>
                    <TableCell className="font-mono text-xs max-w-[150px] truncate">{camera.rtsp_url}</TableCell>
                    <TableCell>
                      <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                        camera.stream_mode === "direct" 
                          ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300" 
                          : camera.stream_mode === "ffmpeg"
                          ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300"
                          : "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300"
                      }`}>
                        {camera.stream_mode || "auto"}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                        camera.is_active 
                          ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300" 
                          : "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300"
                      }`}>
                        {camera.is_active ? "Activa" : "Inactiva"}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${
                        camera.is_recording !== false 
                          ? "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300" 
                          : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400"
                      }`}>
                        {camera.is_recording !== false ? (
                          <>
                            <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                            REC
                          </>
                        ) : (
                          "Pausado"
                        )}
                      </span>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button
                          variant={camera.is_recording !== false ? "outline" : "secondary"}
                          size="sm"
                          onClick={() => handleToggleRecording(camera)}
                          disabled={togglingRecording === camera.id}
                          title={camera.is_recording !== false ? "Detener grabación" : "Reanudar grabación"}
                        >
                          {togglingRecording === camera.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : camera.is_recording !== false ? (
                            <Video className="h-4 w-4 text-red-500" />
                          ) : (
                            <VideoOff className="h-4 w-4 text-gray-400" />
                          )}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openEditDialog(camera)}
                        >
                          Editar
                        </Button>
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => handleDeleteCamera(camera.id)}
                        >
                          Eliminar
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Edit Camera Dialog */}
      <Dialog open={!!editingCamera} onOpenChange={(open) => !open && setEditingCamera(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Editar Cámara</DialogTitle>
            <DialogDescription>
              Modifica la configuración de la cámara
            </DialogDescription>
          </DialogHeader>
          
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="edit-name">Nombre</Label>
              <Input
                id="edit-name"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
              />
            </div>
            
            <div className="grid gap-2">
              <Label htmlFor="edit-url">URL RTSP</Label>
              <Input
                id="edit-url"
                value={editUrl}
                onChange={(e) => setEditUrl(e.target.value)}
              />
            </div>
            
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label>Organización (Tenant)</Label>
                <Select value={editTenantId} onValueChange={setEditTenantId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Seleccionar organización" />
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
              <div className="grid gap-2">
                <Label>Ubicación</Label>
                <Select 
                  value={editLocationId} 
                  onValueChange={setEditLocationId}
                  disabled={!editTenantId}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={editTenantId ? "Seleccionar ubicación" : "Primero seleccione organización"} />
                  </SelectTrigger>
                  <SelectContent>
                    {getEditFilteredLocations().map((location) => (
                      <SelectItem key={location.id} value={location.id.toString()}>
                        {location.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            
            <div className="grid gap-2">
              <Label htmlFor="edit-mode">Modo de Stream</Label>
              <Select value={editMode} onValueChange={setEditMode}>
                <SelectTrigger>
                  <SelectValue placeholder="Seleccionar modo" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="auto">Auto</SelectItem>
                  <SelectItem value="direct">Directo</SelectItem>
                  <SelectItem value="ffmpeg">FFmpeg</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <div className="flex gap-2 items-center flex-wrap">
              <Button 
                type="button" 
                variant="outline"
                size="sm"
                disabled={!editUrl || testingConnection}
                onClick={() => testRtspConnection(editUrl)}
              >
                {testingConnection ? "Probando..." : "Probar Conexión"}
              </Button>
              
              {connectionResult && (
                <span className={`text-sm ${connectionResult.success ? "text-green-600" : "text-red-600"}`}>
                  {connectionResult.success ? "✓ Conexión OK" : "✗ " + connectionResult.message}
                </span>
              )}
            </div>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingCamera(null)}>
              Cancelar
            </Button>
            <Button onClick={handleUpdateCamera} disabled={saving}>
              {saving ? "Guardando..." : "Guardar Cambios"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
