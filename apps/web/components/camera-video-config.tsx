"use client"

import { useState, useEffect } from "react"
import { Settings2, RefreshCw, Save, TestTube2, Loader2, AlertCircle, CheckCircle2, Video, Gauge, Film, Clock } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"
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
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert"
import { Slider } from "@/components/ui/slider"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Separator } from "@/components/ui/separator"

interface Camera {
  id: number
  name: string
  rtsp_url: string
  is_active: boolean
}

interface Resolution {
  width: number
  height: number
}

interface EncoderConfig {
  token: string
  name: string
  encoding: string
  resolution: Resolution
  quality: number
  framerate_limit: number
  bitrate_limit: number
  gov_length: number
  profile: string | null
}

interface EncoderOptions {
  encoding_options: string[]
  resolution_options: Resolution[]
  quality_range: [number, number]
  framerate_range: [number, number]
  bitrate_range: [number, number]
  gov_length_range: [number, number]
  h264_profiles: string[]
  h265_profiles: string[]
}

interface ONVIFConfig {
  host: string
  port: number
  profiles: Array<{
    token: string
    name: string
    video_encoder_token: string | null
  }>
  encoder_configs: EncoderConfig[]
  options: EncoderOptions | null
  error: string | null
}

// Preset configurations for common use cases
const QUALITY_PRESETS = {
  high: { bitrate: 6144, quality: 80, description: "Alta calidad - Mayor tamaño" },
  medium: { bitrate: 3072, quality: 60, description: "Calidad media - Balance" },
  low: { bitrate: 1536, quality: 40, description: "Baja calidad - Menor tamaño" },
  storage: { bitrate: 1024, quality: 30, description: "Ahorro almacenamiento" }
}

export function CameraVideoConfig() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [selectedCamera, setSelectedCamera] = useState<Camera | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  
  // ONVIF credentials
  const [credentials, setCredentials] = useState({
    host: "",
    port: 80,
    username: "",
    password: ""
  })
  
  // ONVIF config data
  const [config, setConfig] = useState<ONVIFConfig | null>(null)
  const [selectedEncoder, setSelectedEncoder] = useState<EncoderConfig | null>(null)
  
  // Edit form state
  const [editForm, setEditForm] = useState({
    encoding: "",
    width: 0,
    height: 0,
    framerate: 0,
    bitrate: 0,
    quality: 0,
    gov_length: 0,
    profile: ""
  })
  
  // Connection state
  const [connectionStatus, setConnectionStatus] = useState<"idle" | "success" | "error">("idle")
  const [statusMessage, setStatusMessage] = useState("")
  
  // Dialog states
  const [showCredentialsDialog, setShowCredentialsDialog] = useState(false)
  
  // Fetch cameras from database
  useEffect(() => {
    fetchCameras()
  }, [])
  
  const fetchCameras = async () => {
    try {
      const response = await fetch(`${API_URL}/api/cameras/`)
      if (response.ok) {
        const data = await response.json()
        setCameras(data)
      }
    } catch (error) {
      console.error("Failed to fetch cameras:", error)
    }
  }
  
  // Extract host from RTSP URL
  const extractHostFromRtsp = (rtspUrl: string): string => {
    try {
      const match = rtspUrl.match(/@([^:/]+)/)
      if (match && match[1]) return match[1]
      const urlMatch = rtspUrl.match(/rtsp:\/\/([^:/]+)/)
      if (urlMatch && urlMatch[1]) return urlMatch[1]
    } catch {}
    return ""
  }
  
  // Handle camera selection
  const handleCameraSelect = (cameraId: string) => {
    const camera = cameras.find(c => c.id.toString() === cameraId)
    if (camera) {
      setSelectedCamera(camera)
      const host = extractHostFromRtsp(camera.rtsp_url)
      setCredentials(prev => ({ ...prev, host }))
      setConfig(null)
      setSelectedEncoder(null)
      setConnectionStatus("idle")
      setShowCredentialsDialog(true)
    }
  }
  
  // Test ONVIF connection
  const testConnection = async () => {
    setTesting(true)
    setConnectionStatus("idle")
    
    try {
      const response = await fetch(`${API_URL}/api/cameras/onvif/test-connection`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(credentials)
      })
      
      const data = await response.json()
      
      if (data.success) {
        setConnectionStatus("success")
        setStatusMessage(`Conexión exitosa. Encontrados ${data.profiles_count} perfiles.`)
      } else {
        setConnectionStatus("error")
        setStatusMessage(data.error || "Error de conexión")
      }
    } catch (error) {
      setConnectionStatus("error")
      setStatusMessage("Error de red")
    } finally {
      setTesting(false)
    }
  }
  
  // Load ONVIF configuration
  const loadConfig = async () => {
    setLoading(true)
    setConfig(null)
    
    try {
      const response = await fetch(`${API_URL}/api/cameras/onvif/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(credentials)
      })
      
      if (response.ok) {
        const data: ONVIFConfig = await response.json()
        setConfig(data)
        setShowCredentialsDialog(false)
        
        // Auto-select first encoder
        if (data.encoder_configs.length > 0 && data.encoder_configs[0]) {
          selectEncoder(data.encoder_configs[0])
        }
      } else {
        const error = await response.json()
        setConnectionStatus("error")
        setStatusMessage(error.detail || "Error al cargar configuración")
      }
    } catch (error) {
      setConnectionStatus("error")
      setStatusMessage("Error de red")
    } finally {
      setLoading(false)
    }
  }
  
  // Select encoder to edit
  const selectEncoder = (encoder: EncoderConfig) => {
    setSelectedEncoder(encoder)
    setEditForm({
      encoding: encoder.encoding,
      width: encoder.resolution.width,
      height: encoder.resolution.height,
      framerate: encoder.framerate_limit,
      bitrate: encoder.bitrate_limit,
      quality: encoder.quality,
      gov_length: encoder.gov_length,
      profile: encoder.profile || ""
    })
  }
  
  // Apply quality preset
  const applyPreset = (presetKey: keyof typeof QUALITY_PRESETS) => {
    const preset = QUALITY_PRESETS[presetKey]
    setEditForm(prev => ({
      ...prev,
      bitrate: Math.min(preset.bitrate, config?.options?.bitrate_range[1] || preset.bitrate),
      quality: preset.quality
    }))
  }
  
  // Save configuration
  const saveConfig = async () => {
    if (!selectedEncoder || !config) return
    
    setSaving(true)
    
    try {
      const response = await fetch(`${API_URL}/api/cameras/onvif/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...credentials,
          config_token: selectedEncoder.token,
          encoding: editForm.encoding,
          width: editForm.width,
          height: editForm.height,
          framerate: editForm.framerate,
          bitrate: editForm.bitrate,
          quality: editForm.quality,
          gov_length: editForm.gov_length,
          profile: editForm.profile || null
        })
      })
      
      if (response.ok) {
        const data = await response.json()
        if (data.success && data.updated_config) {
          // Update local state with new config
          setSelectedEncoder(data.updated_config)
          setConfig(prev => prev ? {
            ...prev,
            encoder_configs: prev.encoder_configs.map(e => 
              e.token === selectedEncoder.token ? data.updated_config : e
            )
          } : null)
          setStatusMessage("Configuración guardada exitosamente")
          setConnectionStatus("success")
        }
      } else {
        const error = await response.json()
        setStatusMessage(error.detail || "Error al guardar")
        setConnectionStatus("error")
      }
    } catch (error) {
      setStatusMessage("Error de red")
      setConnectionStatus("error")
    } finally {
      setSaving(false)
    }
  }
  
  // Format bitrate for display
  const formatBitrate = (kbps: number): string => {
    if (kbps >= 1024) {
      return `${(kbps / 1024).toFixed(1)} Mbps`
    }
    return `${kbps} Kbps`
  }
  
  // Estimate file size for 30 min recording
  const estimateFileSize = (bitrateKbps: number): string => {
    const bytesPerSecond = (bitrateKbps * 1024) / 8
    const seconds = 30 * 60 // 30 minutes
    const bytes = bytesPerSecond * seconds
    const gb = bytes / (1024 * 1024 * 1024)
    if (gb >= 1) {
      return `~${gb.toFixed(1)} GB`
    }
    const mb = bytes / (1024 * 1024)
    return `~${mb.toFixed(0)} MB`
  }
  
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Settings2 className="h-5 w-5" />
          Configuración de Video (ONVIF)
        </CardTitle>
        <CardDescription>
          Configura la resolución, bitrate y codec de tus cámaras IP directamente
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Camera Selection */}
        <div className="space-y-2">
          <Label>Seleccionar Cámara</Label>
          <Select onValueChange={handleCameraSelect} value={selectedCamera?.id.toString() || ""}>
            <SelectTrigger>
              <SelectValue placeholder="Selecciona una cámara para configurar" />
            </SelectTrigger>
            <SelectContent>
              {cameras.map(camera => (
                <SelectItem key={camera.id} value={camera.id.toString()}>
                  {camera.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        
        {/* Status Alert */}
        {connectionStatus !== "idle" && (
          <Alert variant={connectionStatus === "success" ? "default" : "destructive"}>
            {connectionStatus === "success" ? (
              <CheckCircle2 className="h-4 w-4" />
            ) : (
              <AlertCircle className="h-4 w-4" />
            )}
            <AlertTitle>{connectionStatus === "success" ? "Éxito" : "Error"}</AlertTitle>
            <AlertDescription>{statusMessage}</AlertDescription>
          </Alert>
        )}
        
        {/* Show when config loaded but no encoders found */}
        {config && config.encoder_configs.length === 0 && (
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Sin configuración de video</AlertTitle>
            <AlertDescription>
              Se conectó a la cámara pero no se encontraron configuraciones de video.
              Esto puede ocurrir si la cámara no soporta ONVIF Media Service completamente.
              <br />
              <span className="text-xs mt-2 block">
                Perfiles encontrados: {config.profiles.length} | Host: {config.host}
              </span>
            </AlertDescription>
          </Alert>
        )}
        
        {/* Configuration Panel */}
        {config && selectedEncoder && (
          <div className="space-y-6">
            <Separator />
            
            {/* Encoder Selection Tabs */}
            {config.encoder_configs.length > 1 && (
              <Tabs 
                value={selectedEncoder.token} 
                onValueChange={(token) => {
                  const encoder = config.encoder_configs.find(e => e.token === token)
                  if (encoder) selectEncoder(encoder)
                }}
              >
                <TabsList>
                  {config.encoder_configs.map(encoder => (
                    <TabsTrigger key={encoder.token} value={encoder.token}>
                      {encoder.name}
                    </TabsTrigger>
                  ))}
                </TabsList>
              </Tabs>
            )}
            
            {/* Current Config Summary */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Card>
                <CardContent className="pt-4">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Video className="h-4 w-4" />
                    Codec
                  </div>
                  <div className="text-lg font-semibold">{selectedEncoder.encoding}</div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Film className="h-4 w-4" />
                    Resolución
                  </div>
                  <div className="text-lg font-semibold">
                    {selectedEncoder.resolution.width}x{selectedEncoder.resolution.height}
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Gauge className="h-4 w-4" />
                    Bitrate
                  </div>
                  <div className="text-lg font-semibold">{formatBitrate(selectedEncoder.bitrate_limit)}</div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Clock className="h-4 w-4" />
                    30 min
                  </div>
                  <div className="text-lg font-semibold">{estimateFileSize(selectedEncoder.bitrate_limit)}</div>
                </CardContent>
              </Card>
            </div>
            
            {/* Quality Presets */}
            <div className="space-y-2">
              <Label>Presets de Calidad</Label>
              <div className="flex flex-wrap gap-2">
                {Object.entries(QUALITY_PRESETS).map(([key, preset]) => (
                  <Button
                    key={key}
                    variant="outline"
                    size="sm"
                    onClick={() => applyPreset(key as keyof typeof QUALITY_PRESETS)}
                  >
                    {key === "high" && "🔴 Alta"}
                    {key === "medium" && "🟡 Media"}
                    {key === "low" && "🟢 Baja"}
                    {key === "storage" && "💾 Ahorro"}
                  </Button>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">
                Estimación para 30 min: Alta ~1.4GB, Media ~700MB, Baja ~350MB, Ahorro ~230MB
              </p>
            </div>
            
            {/* Edit Form */}
            <div className="grid gap-6 md:grid-cols-2">
              {/* Codec */}
              <div className="space-y-2">
                <Label>Codec de Video</Label>
                <Select 
                  value={editForm.encoding} 
                  onValueChange={(v) => setEditForm(prev => ({ ...prev, encoding: v }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(config.options?.encoding_options || ["H264"]).map(enc => (
                      <SelectItem key={enc} value={enc}>{enc}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  H.265 usa ~50% menos espacio que H.264 pero requiere más CPU
                </p>
              </div>
              
              {/* Resolution */}
              <div className="space-y-2">
                <Label>Resolución</Label>
                <Select 
                  value={`${editForm.width}x${editForm.height}`}
                  onValueChange={(v) => {
                    const parts = v.split("x")
                    const w = parseInt(parts[0] || "0", 10)
                    const h = parseInt(parts[1] || "0", 10)
                    setEditForm(prev => ({ ...prev, width: w, height: h }))
                  }}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(config.options?.resolution_options || []).map(res => (
                      <SelectItem key={`${res.width}x${res.height}`} value={`${res.width}x${res.height}`}>
                        {res.width}x{res.height}
                        {res.width >= 3840 && " (4K)"}
                        {res.width === 2560 && " (2K)"}
                        {res.width === 1920 && " (1080p)"}
                        {res.width === 1280 && " (720p)"}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              {/* Bitrate */}
              <div className="space-y-2">
                <Label>Bitrate: {formatBitrate(editForm.bitrate)}</Label>
                <Slider
                  value={[editForm.bitrate]}
                  onValueChange={(values) => setEditForm(prev => ({ ...prev, bitrate: values[0] ?? prev.bitrate }))}
                  min={config.options?.bitrate_range[0] || 256}
                  max={config.options?.bitrate_range[1] || 16384}
                  step={128}
                />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>{formatBitrate(config.options?.bitrate_range[0] || 256)}</span>
                  <span>Estimado 30 min: {estimateFileSize(editForm.bitrate)}</span>
                  <span>{formatBitrate(config.options?.bitrate_range[1] || 16384)}</span>
                </div>
              </div>
              
              {/* Framerate */}
              <div className="space-y-2">
                <Label>FPS: {editForm.framerate}</Label>
                <Slider
                  value={[editForm.framerate]}
                  onValueChange={(values) => setEditForm(prev => ({ ...prev, framerate: values[0] ?? prev.framerate }))}
                  min={config.options?.framerate_range[0] || 1}
                  max={config.options?.framerate_range[1] || 30}
                  step={1}
                />
                <p className="text-xs text-muted-foreground">
                  15 FPS es suficiente para vigilancia. 25-30 FPS para mayor fluidez.
                </p>
              </div>
              
              {/* Quality */}
              <div className="space-y-2">
                <Label>Calidad: {editForm.quality.toFixed(0)}</Label>
                <Slider
                  value={[editForm.quality]}
                  onValueChange={(values) => setEditForm(prev => ({ ...prev, quality: values[0] ?? prev.quality }))}
                  min={config.options?.quality_range[0] || 1}
                  max={config.options?.quality_range[1] || 100}
                  step={1}
                />
              </div>
              
              {/* GOP / Keyframe Interval */}
              <div className="space-y-2">
                <Label>Intervalo Keyframe (GOP): {editForm.gov_length}</Label>
                <Slider
                  value={[editForm.gov_length]}
                  onValueChange={(values) => setEditForm(prev => ({ ...prev, gov_length: values[0] ?? prev.gov_length }))}
                  min={config.options?.gov_length_range[0] || 1}
                  max={Math.min(config.options?.gov_length_range[1] || 300, 120)}
                  step={1}
                />
                <p className="text-xs text-muted-foreground">
                  Valores más altos = menor tamaño pero peor seeking en reproductor
                </p>
              </div>
            </div>
            
            {/* Save Button */}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => selectEncoder(selectedEncoder)}>
                Restablecer
              </Button>
              <Button onClick={saveConfig} disabled={saving}>
                {saving ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Save className="h-4 w-4 mr-2" />
                )}
                Guardar Configuración
              </Button>
            </div>
          </div>
        )}
      </CardContent>
      
      {/* Credentials Dialog */}
      <Dialog open={showCredentialsDialog} onOpenChange={setShowCredentialsDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Credenciales ONVIF</DialogTitle>
            <DialogDescription>
              Introduce las credenciales de administrador de la cámara para acceder a la configuración.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              <div className="col-span-2 space-y-2">
                <Label>Host / IP</Label>
                <Input 
                  value={credentials.host}
                  onChange={(e) => setCredentials(prev => ({ ...prev, host: e.target.value }))}
                  placeholder="192.168.1.100"
                />
              </div>
              <div className="space-y-2">
                <Label>Puerto ONVIF</Label>
                <Input 
                  type="number"
                  value={credentials.port}
                  onChange={(e) => setCredentials(prev => ({ ...prev, port: parseInt(e.target.value) || 80 }))}
                />
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Usuario</Label>
                <Input 
                  value={credentials.username}
                  onChange={(e) => setCredentials(prev => ({ ...prev, username: e.target.value }))}
                  placeholder="admin"
                />
              </div>
              <div className="space-y-2">
                <Label>Contraseña</Label>
                <Input 
                  type="password"
                  value={credentials.password}
                  onChange={(e) => setCredentials(prev => ({ ...prev, password: e.target.value }))}
                />
              </div>
            </div>
            
            {connectionStatus !== "idle" && (
              <Alert variant={connectionStatus === "success" ? "default" : "destructive"}>
                {connectionStatus === "success" ? (
                  <CheckCircle2 className="h-4 w-4" />
                ) : (
                  <AlertCircle className="h-4 w-4" />
                )}
                <AlertDescription>{statusMessage}</AlertDescription>
              </Alert>
            )}
          </div>
          
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={testConnection} disabled={testing}>
              {testing ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <TestTube2 className="h-4 w-4 mr-2" />
              )}
              Probar Conexión
            </Button>
            <Button onClick={loadConfig} disabled={loading || !credentials.username}>
              {loading ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4 mr-2" />
              )}
              Cargar Configuración
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}
