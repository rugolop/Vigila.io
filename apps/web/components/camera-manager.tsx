"use client"

import { useState, useEffect, useRef } from "react"
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
  address?: string
  tenant_id: number
}

interface DiscoveredCamera {
  ip: string
  port: number
  manufacturer: string | null
  model: string | null
  name: string | null
  onvif_port: number | null
  rtsp_urls: string[]
  discovery_method: string
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

export const CameraManager = () => {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [newCameraName, setNewCameraName] = useState("")
  const [newCameraUrl, setNewCameraUrl] = useState("")
  const [loading, setLoading] = useState(false)
  
  // Tenant and Location state
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [locations, setLocations] = useState<Location[]>([])
  const [selectedTenantId, setSelectedTenantId] = useState<string>("")
  const [selectedLocationId, setSelectedLocationId] = useState<string>("")
  const [filteredLocations, setFilteredLocations] = useState<Location[]>([])
  
  // Discovery state
  const [discoveredCameras, setDiscoveredCameras] = useState<DiscoveredCamera[]>([])
  const [discovering, setDiscovering] = useState(false)
  const [networkRange, setNetworkRange] = useState("192.168.1.0/24")
  const [addingCamera, setAddingCamera] = useState<string | null>(null)
  
  // Edit state
  const [editingCamera, setEditingCamera] = useState<Camera | null>(null)
  const [editName, setEditName] = useState("")
  const [editUrl, setEditUrl] = useState("")
  const [editMode, setEditMode] = useState("")
  const [editTenantId, setEditTenantId] = useState<string>("")
  const [editLocationId, setEditLocationId] = useState<string>("")
  const [saving, setSaving] = useState(false)
  
  // Add discovered camera with custom name
  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [selectedDiscoveredCamera, setSelectedDiscoveredCamera] = useState<DiscoveredCamera | null>(null)
  const [selectedRtspUrl, setSelectedRtspUrl] = useState("")
  const [customCameraName, setCustomCameraName] = useState("")
  const [dialogTenantId, setDialogTenantId] = useState<string>("")
  const [dialogLocationId, setDialogLocationId] = useState<string>("")
  
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

  // Get filtered locations for add discovered dialog
  const getDialogFilteredLocations = () => {
    if (dialogTenantId) {
      return locations.filter(loc => loc.tenant_id === parseInt(dialogTenantId))
    }
    return []
  }

  const fetchCameras = async () => {
    try {
      const response = await fetch(`${API_URL}/api/cameras`)
      if (response.ok) {
        const data = await response.json()
        setCameras(data)
      }
    } catch (error) {
      console.error("Failed to fetch cameras", error)
    }
  }

  const discoverCameras = async () => {
    setDiscovering(true)
    try {
      const response = await fetch(
        `${API_URL}/api/camerasdiscover?use_onvif=true&use_port_scan=true&network_range=${encodeURIComponent(networkRange)}`,
        { method: "POST" }
      )
      if (response.ok) {
        const data = await response.json()
        setDiscoveredCameras(data.cameras || [])
      }
    } catch (error) {
      console.error("Failed to discover cameras", error)
    } finally {
      setDiscovering(false)
    }
  }

  const testRtspConnection = async (rtspUrl: string) => {
    setTestingConnection(true)
    setConnectionResult(null)
    try {
      const response = await fetch(`${API_URL}/api/camerastest-rtsp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rtsp_url: rtspUrl, timeout: 5 }),
      })
      if (response.ok) {
        const result = await response.json()
        setConnectionResult(result)
      } else {
        setConnectionResult({ success: false, message: "Error al probar conexión" })
      }
    } catch (error) {
      setConnectionResult({ success: false, message: "Error de red" })
    } finally {
      setTestingConnection(false)
    }
  }

  const openAddDialog = (camera: DiscoveredCamera, rtspUrl: string) => {
    setSelectedDiscoveredCamera(camera)
    setSelectedRtspUrl(rtspUrl)
    setCustomCameraName(
      camera.name || camera.manufacturer 
        ? `${camera.manufacturer || "Camera"} ${camera.ip.split('.').pop()}`
        : `Camera ${camera.ip.split('.').pop()}`
    )
    setDialogTenantId("")
    setDialogLocationId("")
    setConnectionResult(null)
    setAddDialogOpen(true)
  }

  const handleAddDiscoveredCamera = async () => {
    if (!selectedDiscoveredCamera) return
    
    setAddingCamera(selectedDiscoveredCamera.ip)
    try {
      const response = await fetch(`${API_URL}/api/cameras`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: customCameraName,
          rtsp_url: selectedRtspUrl,
          is_active: true,
          tenant_id: dialogTenantId ? parseInt(dialogTenantId) : null,
          location_id: dialogLocationId ? parseInt(dialogLocationId) : null,
        }),
      })

      if (response.ok) {
        fetchCameras()
        setDiscoveredCameras(prev => prev.filter(c => c.ip !== selectedDiscoveredCamera.ip))
        setAddDialogOpen(false)
        setSelectedDiscoveredCamera(null)
      }
    } catch (error) {
      console.error("Failed to add discovered camera", error)
    } finally {
      setAddingCamera(null)
    }
  }

  const addDiscoveredCamera = async (camera: DiscoveredCamera, rtspUrl: string) => {
    // Open dialog instead of adding directly
    openAddDialog(camera, rtspUrl)
  }

  const handleAddCamera = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/api/cameras`, {
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
    if (!confirm("¿Estás seguro de que deseas eliminar esta cámara?")) {
      return
    }

    try {
      const response = await fetch(`${API_URL}/api/cameras${cameraId}`, {
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
      const response = await fetch(`${API_URL}/api/cameras${camera.id}/recording/toggle`, {
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

  const openEditDialog = (camera: Camera) => {
    setEditingCamera(camera)
    setEditName(camera.name)
    setEditUrl(camera.rtsp_url)
    setEditMode(camera.stream_mode || "auto")
    setEditTenantId(camera.tenant_id?.toString() || "")
    setEditLocationId(camera.location_id?.toString() || "")
    setConnectionResult(null)
  }

  const handleUpdateCamera = async () => {
    if (!editingCamera) return
    
    setSaving(true)
    try {
      const response = await fetch(`${API_URL}/api/cameras${editingCamera.id}`, {
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

  useEffect(() => {
    fetchCameras()
    fetchTenants()
    fetchLocations()
  }, [])

  return (
    <div className="grid gap-8">
      {/* Network Discovery Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"/>
              <path d="M12 6v6l4 2"/>
            </svg>
            Descubrir Cámaras
          </CardTitle>
          <CardDescription>
            Escanea tu red local para encontrar cámaras IP automáticamente
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4 items-end mb-4">
            <div className="grid gap-2 flex-1">
              <Label htmlFor="network">Rango de Red (CIDR)</Label>
              <Input
                id="network"
                placeholder="192.168.1.0/24"
                value={networkRange}
                onChange={(e) => setNetworkRange(e.target.value)}
              />
            </div>
            <Button onClick={discoverCameras} disabled={discovering}>
              {discovering ? (
                <>
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Escaneando...
                </>
              ) : (
                "Escanear Red"
              )}
            </Button>
          </div>

          {discoveredCameras.length > 0 && (
            <div className="border rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>IP</TableHead>
                    <TableHead>Puerto</TableHead>
                    <TableHead>Fabricante</TableHead>
                    <TableHead>Método</TableHead>
                    <TableHead>URL RTSP</TableHead>
                    <TableHead>Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {discoveredCameras.map((camera) => (
                    <TableRow key={camera.ip}>
                      <TableCell className="font-mono">{camera.ip}</TableCell>
                      <TableCell>{camera.port}</TableCell>
                      <TableCell>{camera.manufacturer || "Desconocido"}</TableCell>
                      <TableCell>
                        <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                          camera.discovery_method === "onvif" 
                            ? "bg-blue-100 text-blue-800" 
                            : "bg-gray-100 text-gray-800"
                        }`}>
                          {camera.discovery_method === "onvif" ? "ONVIF" : "Port Scan"}
                        </span>
                      </TableCell>
                      <TableCell>
                        <select 
                          className="text-xs border rounded p-1 max-w-[200px]"
                          defaultValue={camera.rtsp_urls[0]}
                          id={`url-${camera.ip}`}
                        >
                          {camera.rtsp_urls.map((url, i) => (
                            <option key={i} value={url}>{url.replace(`rtsp://${camera.ip}:${camera.port}`, '')}</option>
                          ))}
                        </select>
                      </TableCell>
                      <TableCell>
                        <Button
                          size="sm"
                          disabled={addingCamera === camera.ip}
                          onClick={() => {
                            const select = document.getElementById(`url-${camera.ip}`) as HTMLSelectElement
                            openAddDialog(camera, select.value)
                          }}
                        >
                          Agregar
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          {!discovering && discoveredCameras.length === 0 && (
            <p className="text-sm text-gray-500 text-center py-4">
              Haz clic en "Escanear Red" para descubrir cámaras en tu red
            </p>
          )}
        </CardContent>
      </Card>

      {/* Manual Add Section */}
      <Card>
        <CardHeader>
          <CardTitle>Agregar Cámara Manualmente</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAddCamera} className="grid gap-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="name">Nombre de Cámara</Label>
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
                <Label htmlFor="tenant">Organización (Tenant)</Label>
                <Select 
                  value={selectedTenantId} 
                  onValueChange={(val) => setSelectedTenantId(val)}
                >
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
                <Label htmlFor="location">Ubicación</Label>
                <Select 
                  value={selectedLocationId} 
                  onValueChange={(val) => setSelectedLocationId(val)}
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
                {loading ? "Agregando..." : "Agregar Cámara"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Cámaras Conectadas</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Nombre</TableHead>
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
                  <TableCell colSpan={7} className="text-center text-gray-500">
                    No se encontraron cámaras.
                  </TableCell>
                </TableRow>
              ) : (
                cameras.map((camera) => (
                  <TableRow key={camera.id}>
                    <TableCell>{camera.id}</TableCell>
                    <TableCell className="font-medium">{camera.name}</TableCell>
                    <TableCell className="font-mono text-xs max-w-[200px] truncate">{camera.rtsp_url}</TableCell>
                    <TableCell>
                      <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                        camera.stream_mode === "direct" 
                          ? "bg-green-100 text-green-800" 
                          : camera.stream_mode === "ffmpeg"
                          ? "bg-yellow-100 text-yellow-800"
                          : "bg-gray-100 text-gray-800"
                      }`}>
                        {camera.stream_mode || "auto"}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                        camera.is_active ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
                      }`}>
                        {camera.is_active ? "Activa" : "Inactiva"}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${
                        camera.is_recording !== false ? "bg-red-100 text-red-800" : "bg-gray-100 text-gray-500"
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
                <Select 
                  value={editTenantId} 
                  onValueChange={(val) => setEditTenantId(val)}
                >
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
                  onValueChange={(val) => setEditLocationId(val)}
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
              <select
                id="edit-mode"
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={editMode}
                onChange={(e) => setEditMode(e.target.value)}
              >
                <option value="auto">Auto</option>
                <option value="direct">Directo</option>
                <option value="ffmpeg">FFmpeg</option>
              </select>
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

      {/* Add Discovered Camera Dialog */}
      <Dialog open={addDialogOpen} onOpenChange={(open) => !open && setAddDialogOpen(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Agregar Cámara Descubierta</DialogTitle>
            <DialogDescription>
              Personaliza el nombre antes de agregar
            </DialogDescription>
          </DialogHeader>
          
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="custom-name">Nombre de Cámara</Label>
              <Input
                id="custom-name"
                value={customCameraName}
                onChange={(e) => setCustomCameraName(e.target.value)}
                placeholder="Nombre personalizado"
              />
            </div>
            
            <div className="grid gap-2">
              <Label>URL RTSP</Label>
              <code className="text-xs bg-gray-100 dark:bg-gray-800 p-2 rounded break-all">
                {selectedRtspUrl}
              </code>
            </div>
            
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label>Organización (Tenant)</Label>
                <Select 
                  value={dialogTenantId} 
                  onValueChange={(val) => setDialogTenantId(val)}
                >
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
                  value={dialogLocationId} 
                  onValueChange={(val) => setDialogLocationId(val)}
                  disabled={!dialogTenantId}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={dialogTenantId ? "Seleccionar ubicación" : "Primero seleccione organización"} />
                  </SelectTrigger>
                  <SelectContent>
                    {getDialogFilteredLocations().map((location) => (
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
                size="sm"
                disabled={testingConnection}
                onClick={() => testRtspConnection(selectedRtspUrl)}
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
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddDialogOpen(false)}>
              Cancelar
            </Button>
            <Button 
              onClick={handleAddDiscoveredCamera} 
              disabled={addingCamera !== null || !customCameraName}
            >
              {addingCamera ? "Agregando..." : "Agregar Cámara"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
