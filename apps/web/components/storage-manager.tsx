"use client"

import { useState, useEffect, useCallback, useMemo } from "react"
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
  DialogTrigger,
} from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Separator } from "@/components/ui/separator"
import {
  HardDrive,
  Server,
  Usb,
  Cloud,
  Plus,
  RefreshCw,
  Star,
  Trash2,
  AlertCircle,
  CheckCircle2,
  FolderOpen,
  Settings,
  Clock,
  AlertTriangle,
  Loader2,
  Database,
  Film,
} from "lucide-react"
import { Slider } from "@/components/ui/slider"
import {
  ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"
import { PieChart, Pie, Cell, ResponsiveContainer, Label as RechartsLabel } from "recharts"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"

interface StorageVolume {
  id: number
  name: string
  storage_type: string
  mount_path: string | null
  is_primary: boolean
  is_active: boolean
  status: string
  host_path: string | null
  server_address: string | null
  share_name: string | null
  username: string | null
  total_bytes: number | null
  used_bytes: number | null
  retention_days: number
  created_at: string
  last_checked: string | null
}

interface StorageOverview {
  volumes: StorageVolume[]
  total_storage_bytes: number
  total_used_bytes: number
  total_free_bytes: number
  total_recordings: number
  primary_volume_id: number | null
}

interface StorageTypeInfo {
  type: string
  name: string
  description: string
  fields: string[]
  hint?: string
  icon: string
}

interface RetentionAnalysis {
  volume_id: number
  volume_name: string
  mount_path: string
  current_retention_days: number
  recommended_retention_days: number
  storage: {
    total_bytes: number
    used_bytes: number
    free_bytes: number
    usage_percent: number
    free_percent: number
  }
  recordings: {
    total_bytes: number
    oldest_days: number
    days_breakdown: Array<{age_days: number, size_bytes: number, count: number}>
  }
  cameras: {
    active_count: number
    estimated_gb_per_camera_per_day: number
  }
  warnings: Array<{level: string, message: string}>
  can_increase_retention: boolean
}

interface CleanupStatus {
  is_running: boolean
  last_run: string | null
  last_files_deleted: number
  last_bytes_freed: number
  next_run: string | null
}

const STORAGE_ICONS: Record<string, React.ReactNode> = {
  local: <FolderOpen className="h-5 w-5" />,
  nas_smb: <Server className="h-5 w-5" />,
  nas_nfs: <Server className="h-5 w-5" />,
  usb: <Usb className="h-5 w-5" />,
  s3: <Cloud className="h-5 w-5" />,
  azure: <Cloud className="h-5 w-5" />,
  gcs: <Cloud className="h-5 w-5" />,
}

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  inactive: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300",
  error: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
  full: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
}

const STATUS_LABELS: Record<string, string> = {
  active: "Activo",
  inactive: "Inactivo",
  error: "Error",
  full: "Lleno",
}

function formatBytes(bytes: number | null): string {
  if (bytes === null || bytes === 0) return "0 B"
  const k = 1024
  const sizes = ["B", "KB", "MB", "GB", "TB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
}

function getUsagePercent(used: number | null, total: number | null): number {
  if (!used || !total || total === 0) return 0
  return Math.round((used / total) * 100)
}

export function StorageManager() {
  const [overview, setOverview] = useState<StorageOverview | null>(null)
  const [storageTypes, setStorageTypes] = useState<StorageTypeInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [showAddDialog, setShowAddDialog] = useState(false)
  const [checkingId, setCheckingId] = useState<number | null>(null)
  const [selectedVolumeId, setSelectedVolumeId] = useState<number | null>(null)
  
  // Form state
  const [formData, setFormData] = useState({
    name: "",
    storage_type: "local",
    host_path: "",
    server_address: "",
    share_name: "",
    username: "",
    password: "",
    retention_days: 7,
    is_primary: false,
  })
  const [formError, setFormError] = useState("")
  const [submitting, setSubmitting] = useState(false)
  
  // Retention management state
  const [retentionAnalysis, setRetentionAnalysis] = useState<Record<number, RetentionAnalysis>>({})
  const [cleanupStatus, setCleanupStatus] = useState<CleanupStatus | null>(null)
  const [updatingRetention, setUpdatingRetention] = useState<number | null>(null)
  const [runningCleanup, setRunningCleanup] = useState(false)
  const [expandedVolume, setExpandedVolume] = useState<number | null>(null)
  
  // Get selected volume data
  const selectedVolume = useMemo(() => {
    if (!overview?.volumes || overview.volumes.length === 0) return null
    if (selectedVolumeId) {
      return overview.volumes.find(v => v.id === selectedVolumeId) || null
    }
    // Default to primary or first volume
    return overview.volumes.find(v => v.is_primary) || overview.volumes[0] || null
  }, [overview?.volumes, selectedVolumeId])
  
  // Auto-select primary volume when overview loads
  useEffect(() => {
    if (overview?.volumes && overview.volumes.length > 0 && !selectedVolumeId) {
      const primary = overview.volumes.find(v => v.is_primary)
      if (primary) {
        setSelectedVolumeId(primary.id)
      } else {
        setSelectedVolumeId(overview.volumes[0]?.id || null)
      }
    }
  }, [overview?.volumes, selectedVolumeId])
  
  // Chart config
  const storageChartConfig = {
    used: {
      label: "Usado",
      color: "hsl(var(--chart-1))",
    },
    free: {
      label: "Libre",
      color: "hsl(var(--chart-2))",
    },
  } satisfies ChartConfig
  
  // Chart data for selected volume
  const storageChartData = useMemo(() => {
    if (!selectedVolume) return []
    const used = selectedVolume.used_bytes || 0
    const total = selectedVolume.total_bytes || 0
    const free = total - used
    return [
      { name: "Usado", value: used, fill: "hsl(var(--chart-1))" },
      { name: "Libre", value: free, fill: "hsl(var(--chart-2))" },
    ]
  }, [selectedVolume])
  
  const fetchOverview = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/storage/overview`)
      if (response.ok) {
        const data = await response.json()
        setOverview(data)
      }
    } catch (error) {
      console.error("Error fetching storage overview:", error)
    } finally {
      setLoading(false)
    }
  }, [])
  
  const fetchStorageTypes = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/storage/types/info`)
      if (response.ok) {
        const data = await response.json()
        setStorageTypes(data.types)
      }
    } catch (error) {
      console.error("Error fetching storage types:", error)
    }
  }, [])
  
  useEffect(() => {
    fetchOverview()
    fetchStorageTypes()
  }, [fetchOverview, fetchStorageTypes])
  
  // Fetch retention analysis for a volume
  const fetchRetentionAnalysis = async (volumeId: number) => {
    try {
      const response = await fetch(`${API_URL}/storage/${volumeId}/retention/analysis`)
      if (response.ok) {
        const data = await response.json()
        setRetentionAnalysis(prev => ({ ...prev, [volumeId]: data }))
      }
    } catch (error) {
      console.error("Error fetching retention analysis:", error)
    }
  }
  
  // Fetch cleanup status
  const fetchCleanupStatus = async () => {
    try {
      const response = await fetch(`${API_URL}/storage/cleanup/status`)
      if (response.ok) {
        const data = await response.json()
        setCleanupStatus(data)
      }
    } catch (error) {
      console.error("Error fetching cleanup status:", error)
    }
  }
  
  // Update retention for a volume
  const handleUpdateRetention = async (volumeId: number, retentionDays: number, autoAdjust: boolean = true) => {
    setUpdatingRetention(volumeId)
    try {
      const response = await fetch(`${API_URL}/storage/${volumeId}/retention`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ retention_days: retentionDays, auto_adjust: autoAdjust }),
      })
      if (response.ok) {
        const data = await response.json()
        // Update local state with new analysis
        setRetentionAnalysis(prev => ({ ...prev, [volumeId]: data }))
        await fetchOverview()
      }
    } catch (error) {
      console.error("Error updating retention:", error)
    } finally {
      setUpdatingRetention(null)
    }
  }
  
  // Trigger manual cleanup for a volume
  const handleManualCleanup = async (volumeId: number) => {
    if (!confirm("¿Ejecutar limpieza manual? Se eliminarán grabaciones antiguas según la política de retención.")) {
      return
    }
    setRunningCleanup(true)
    try {
      const response = await fetch(`${API_URL}/storage/${volumeId}/cleanup`, {
        method: "POST",
      })
      if (response.ok) {
        const data = await response.json()
        alert(`Limpieza completada: ${data.files_deleted} archivos eliminados, ${formatBytes(data.bytes_freed)} liberados`)
        await fetchOverview()
        await fetchRetentionAnalysis(volumeId)
      }
    } catch (error) {
      console.error("Error running cleanup:", error)
      alert("Error al ejecutar limpieza")
    } finally {
      setRunningCleanup(false)
    }
  }
  
  // Toggle volume expansion and load analysis
  const toggleVolumeExpansion = async (volumeId: number) => {
    if (expandedVolume === volumeId) {
      setExpandedVolume(null)
    } else {
      setExpandedVolume(volumeId)
      if (!retentionAnalysis[volumeId]) {
        await fetchRetentionAnalysis(volumeId)
      }
    }
  }
  
  // Fetch cleanup status on mount
  useEffect(() => {
    fetchCleanupStatus()
    const interval = setInterval(fetchCleanupStatus, 60000) // Update every minute
    return () => clearInterval(interval)
  }, [])
  
  const handleCheckVolume = async (volumeId: number) => {
    setCheckingId(volumeId)
    try {
      await fetch(`${API_URL}/storage/${volumeId}/check`, {
        method: "POST",
      })
      await fetchOverview()
    } catch (error) {
      console.error("Error checking volume:", error)
    } finally {
      setCheckingId(null)
    }
  }
  
  const handleSetPrimary = async (volumeId: number) => {
    try {
      await fetch(`${API_URL}/storage/${volumeId}/set-primary`, {
        method: "POST",
      })
      await fetchOverview()
    } catch (error) {
      console.error("Error setting primary:", error)
    }
  }
  
  const handleDelete = async (volumeId: number, volumeName: string) => {
    if (!confirm(`¿Eliminar el volumen "${volumeName}"? Las grabaciones existentes NO se eliminarán.`)) {
      return
    }
    try {
      const response = await fetch(`${API_URL}/storage/${volumeId}`, {
        method: "DELETE",
      })
      if (response.ok) {
        await fetchOverview()
      } else {
        const error = await response.json()
        alert(error.detail || "Error al eliminar")
      }
    } catch (error) {
      console.error("Error deleting volume:", error)
    }
  }
  
  const handleAddVolume = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError("")
    setSubmitting(true)
    
    try {
      const payload: Record<string, unknown> = {
        name: formData.name,
        storage_type: formData.storage_type,
        retention_days: formData.retention_days,
        is_primary: formData.is_primary,
      }
      
      // Add type-specific fields
      if (formData.storage_type === "local" || formData.storage_type === "usb") {
        payload.host_path = formData.host_path
      } else if (formData.storage_type === "nas_smb") {
        payload.server_address = formData.server_address
        payload.share_name = formData.share_name
        payload.username = formData.username
        payload.password = formData.password
      } else if (formData.storage_type === "nas_nfs") {
        payload.server_address = formData.server_address
        payload.share_name = formData.share_name
      } else if (formData.storage_type === "s3") {
        payload.server_address = formData.server_address // endpoint
        payload.share_name = formData.share_name // bucket
        payload.username = formData.username // access key
        payload.password = formData.password // secret key
      }
      
      const response = await fetch(`${API_URL}/storage/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
      
      if (response.ok) {
        setShowAddDialog(false)
        setFormData({
          name: "",
          storage_type: "local",
          host_path: "",
          server_address: "",
          share_name: "",
          username: "",
          password: "",
          retention_days: 7,
          is_primary: false,
        })
        await fetchOverview()
      } else {
        const error = await response.json()
        setFormError(error.detail || "Error al crear volumen")
      }
    } catch (error) {
      setFormError("Error de conexión")
    } finally {
      setSubmitting(false)
    }
  }
  
  const selectedTypeInfo = storageTypes.find(t => t.type === formData.storage_type)
  
  if (loading) {
    return (
      <Card>
        <CardContent className="py-10">
          <div className="flex items-center justify-center">
            <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    )
  }
  
  return (
    <div className="space-y-6">
      {/* Storage Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
              <HardDrive className="h-4 w-4" />
              Almacenamiento Total
            </div>
            <div className="text-2xl font-bold">
              {formatBytes(overview?.total_storage_bytes || 0)}
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
              <FolderOpen className="h-4 w-4" />
              Espacio Usado
            </div>
            <div className="text-2xl font-bold">
              {formatBytes(overview?.total_used_bytes || 0)}
            </div>
            <Progress 
              value={getUsagePercent(overview?.total_used_bytes || 0, overview?.total_storage_bytes || 0)} 
              className="h-2 mt-2" 
            />
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
              <CheckCircle2 className="h-4 w-4" />
              Espacio Libre
            </div>
            <div className="text-2xl font-bold text-green-600">
              {formatBytes(overview?.total_free_bytes || 0)}
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
              <Settings className="h-4 w-4" />
              Grabaciones
            </div>
            <div className="text-2xl font-bold">
              {overview?.total_recordings || 0}
            </div>
      </CardContent>
        </Card>
      </div>
      
      {/* Cleanup Status Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Limpieza Automática
          </CardTitle>
          <CardDescription>
            El sistema limpia automáticamente las grabaciones antiguas según la política de retención
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="text-center p-3 bg-muted rounded-lg">
              <div className="text-sm text-muted-foreground mb-1">Estado</div>
              <div className={`font-medium ${cleanupStatus?.is_running ? 'text-yellow-600' : 'text-green-600'}`}>
                {cleanupStatus?.is_running ? 'Ejecutando...' : 'En espera'}
              </div>
            </div>
            <div className="text-center p-3 bg-muted rounded-lg">
              <div className="text-sm text-muted-foreground mb-1">Última ejecución</div>
              <div className="font-medium">
                {cleanupStatus?.last_run 
                  ? new Date(cleanupStatus.last_run).toLocaleString() 
                  : 'Nunca'}
              </div>
            </div>
            <div className="text-center p-3 bg-muted rounded-lg">
              <div className="text-sm text-muted-foreground mb-1">Archivos eliminados</div>
              <div className="font-medium">{cleanupStatus?.last_files_deleted || 0}</div>
            </div>
            <div className="text-center p-3 bg-muted rounded-lg">
              <div className="text-sm text-muted-foreground mb-1">Espacio liberado</div>
              <div className="font-medium">{formatBytes(cleanupStatus?.last_bytes_freed || 0)}</div>
            </div>
          </div>
        </CardContent>
      </Card>
      
      {/* Volumes Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <HardDrive className="h-5 w-5" />
                Volúmenes de Almacenamiento
              </CardTitle>
              <CardDescription>
                Gestiona los volúmenes donde se guardan las grabaciones
              </CardDescription>
            </div>
            <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  Agregar Volumen
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-125">
                <DialogHeader>
                  <DialogTitle>Agregar Volumen de Almacenamiento</DialogTitle>
                  <DialogDescription>
                    Configura un nuevo volumen para almacenar grabaciones
                  </DialogDescription>
                </DialogHeader>
                <form onSubmit={handleAddVolume}>
                  <div className="grid gap-4 py-4">
                    <div className="grid gap-2">
                      <Label htmlFor="name">Nombre</Label>
                      <Input
                        id="name"
                        placeholder="ej. NAS Principal"
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        required
                      />
                    </div>
                    
                    <div className="grid gap-2">
                      <Label htmlFor="type">Tipo de Almacenamiento</Label>
                      <Select
                        value={formData.storage_type}
                        onValueChange={(v) => setFormData({ ...formData, storage_type: v })}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {storageTypes.map((type) => (
                            <SelectItem key={type.type} value={type.type}>
                              <div className="flex items-center gap-2">
                                {STORAGE_ICONS[type.type]}
                                {type.name}
                              </div>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {selectedTypeInfo && (
                        <p className="text-xs text-muted-foreground">
                          {selectedTypeInfo.description}
                        </p>
                      )}
                    </div>
                    
                    <Separator />
                    
                    {/* Dynamic fields based on type */}
                    {(formData.storage_type === "local" || formData.storage_type === "usb") && (
                      <div className="grid gap-2">
                        <Label htmlFor="host_path">Ruta en Host</Label>
                        <Input
                          id="host_path"
                          placeholder="/mnt/storage o D:\Recordings"
                          value={formData.host_path}
                          onChange={(e) => setFormData({ ...formData, host_path: e.target.value })}
                          required
                        />
                        <p className="text-xs text-muted-foreground">
                          Ruta absoluta en la máquina host donde se montará
                        </p>
                      </div>
                    )}
                    
                    {formData.storage_type === "nas_smb" && (
                      <>
                        <div className="grid gap-2">
                          <Label htmlFor="server_address">Servidor</Label>
                          <Input
                            id="server_address"
                            placeholder="192.168.1.100 o nas.local"
                            value={formData.server_address}
                            onChange={(e) => setFormData({ ...formData, server_address: e.target.value })}
                            required
                          />
                        </div>
                        <div className="grid gap-2">
                          <Label htmlFor="share_name">Nombre del Share</Label>
                          <Input
                            id="share_name"
                            placeholder="recordings"
                            value={formData.share_name}
                            onChange={(e) => setFormData({ ...formData, share_name: e.target.value })}
                            required
                          />
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                          <div className="grid gap-2">
                            <Label htmlFor="username">Usuario</Label>
                            <Input
                              id="username"
                              value={formData.username}
                              onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                            />
                          </div>
                          <div className="grid gap-2">
                            <Label htmlFor="password">Contraseña</Label>
                            <Input
                              id="password"
                              type="password"
                              value={formData.password}
                              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                            />
                          </div>
                        </div>
                      </>
                    )}
                    
                    {formData.storage_type === "nas_nfs" && (
                      <>
                        <div className="grid gap-2">
                          <Label htmlFor="server_address">Servidor</Label>
                          <Input
                            id="server_address"
                            placeholder="192.168.1.100"
                            value={formData.server_address}
                            onChange={(e) => setFormData({ ...formData, server_address: e.target.value })}
                            required
                          />
                        </div>
                        <div className="grid gap-2">
                          <Label htmlFor="share_name">Ruta Export</Label>
                          <Input
                            id="share_name"
                            placeholder="/export/recordings"
                            value={formData.share_name}
                            onChange={(e) => setFormData({ ...formData, share_name: e.target.value })}
                            required
                          />
                        </div>
                      </>
                    )}
                    
                    {formData.storage_type === "s3" && (
                      <>
                        <div className="grid gap-2">
                          <Label htmlFor="server_address">Endpoint</Label>
                          <Input
                            id="server_address"
                            placeholder="s3.amazonaws.com o minio.local:9000"
                            value={formData.server_address}
                            onChange={(e) => setFormData({ ...formData, server_address: e.target.value })}
                            required
                          />
                        </div>
                        <div className="grid gap-2">
                          <Label htmlFor="share_name">Bucket</Label>
                          <Input
                            id="share_name"
                            placeholder="my-recordings-bucket"
                            value={formData.share_name}
                            onChange={(e) => setFormData({ ...formData, share_name: e.target.value })}
                            required
                          />
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                          <div className="grid gap-2">
                            <Label htmlFor="username">Access Key</Label>
                            <Input
                              id="username"
                              value={formData.username}
                              onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                              required
                            />
                          </div>
                          <div className="grid gap-2">
                            <Label htmlFor="password">Secret Key</Label>
                            <Input
                              id="password"
                              type="password"
                              value={formData.password}
                              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                              required
                            />
                          </div>
                        </div>
                      </>
                    )}
                    
                    <Separator />
                    
                    <div className="grid grid-cols-2 gap-4">
                      <div className="grid gap-2">
                        <Label htmlFor="retention">Retención (días)</Label>
                        <Input
                          id="retention"
                          type="number"
                          min="1"
                          max="365"
                          value={formData.retention_days}
                          onChange={(e) => setFormData({ ...formData, retention_days: parseInt(e.target.value) || 7 })}
                        />
                      </div>
                      <div className="flex items-center gap-2 pt-8">
                        <input
                          type="checkbox"
                          id="is_primary"
                          checked={formData.is_primary}
                          onChange={(e) => setFormData({ ...formData, is_primary: e.target.checked })}
                          className="h-4 w-4"
                        />
                        <Label htmlFor="is_primary" className="font-normal">
                          Volumen primario
                        </Label>
                      </div>
                    </div>
                    
                    {formError && (
                      <Alert variant="destructive">
                        <AlertCircle className="h-4 w-4" />
                        <AlertDescription>{formError}</AlertDescription>
                      </Alert>
                    )}
                  </div>
                  <DialogFooter>
                    <Button type="button" variant="outline" onClick={() => setShowAddDialog(false)}>
                      Cancelar
                    </Button>
                    <Button type="submit" disabled={submitting}>
                      {submitting ? "Creando..." : "Crear Volumen"}
                    </Button>
                  </DialogFooter>
                </form>
              </DialogContent>
            </Dialog>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nombre</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Ruta/Servidor</TableHead>
                <TableHead>Uso</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Retención</TableHead>
                <TableHead className="text-right">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(!overview?.volumes || overview.volumes.length === 0) ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                    No hay volúmenes configurados
                  </TableCell>
                </TableRow>
              ) : (
                overview.volumes.map((volume) => (
                  <>
                    <TableRow 
                      key={volume.id} 
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => toggleVolumeExpansion(volume.id)}
                    >
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {volume.is_primary && (
                            <Star className="h-4 w-4 text-yellow-500 fill-yellow-500" />
                          )}
                          <span className="font-medium">{volume.name}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {STORAGE_ICONS[volume.storage_type]}
                          <span className="text-sm">
                            {storageTypes.find(t => t.type === volume.storage_type)?.name || volume.storage_type}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {volume.server_address 
                          ? `${volume.server_address}/${volume.share_name || ''}`
                          : volume.host_path || volume.mount_path
                        }
                      </TableCell>
                      <TableCell>
                        <div className="w-32">
                          <div className="text-xs text-muted-foreground mb-1">
                            {formatBytes(volume.used_bytes)} / {formatBytes(volume.total_bytes)}
                          </div>
                          <Progress 
                            value={getUsagePercent(volume.used_bytes, volume.total_bytes)} 
                            className="h-2" 
                          />
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge className={STATUS_COLORS[volume.status] || ""}>
                          {STATUS_LABELS[volume.status] || volume.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          className="gap-1"
                          onClick={(e) => { e.stopPropagation(); toggleVolumeExpansion(volume.id); }}
                        >
                          <Clock className="h-3 w-3" />
                          {volume.retention_days} días
                        </Button>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleCheckVolume(volume.id)}
                            disabled={checkingId === volume.id}
                            title="Verificar estado"
                          >
                            <RefreshCw className={`h-4 w-4 ${checkingId === volume.id ? 'animate-spin' : ''}`} />
                          </Button>
                          {!volume.is_primary && (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleSetPrimary(volume.id)}
                              title="Establecer como primario"
                            >
                              <Star className="h-4 w-4" />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDelete(volume.id, volume.name)}
                            className="text-destructive"
                            title="Eliminar"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                    {/* Expanded retention settings */}
                    {expandedVolume === volume.id && (
                      <TableRow key={`${volume.id}-expanded`}>
                        <TableCell colSpan={7} className="bg-muted/30 p-4">
                          <div className="space-y-4">
                            <div className="flex items-center justify-between">
                              <h4 className="font-medium flex items-center gap-2">
                                <Settings className="h-4 w-4" />
                                Configuración de Retención - {volume.name}
                              </h4>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleManualCleanup(volume.id)}
                                disabled={runningCleanup}
                              >
                                {runningCleanup ? (
                                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                ) : (
                                  <Trash2 className="h-4 w-4 mr-2" />
                                )}
                                Limpiar ahora
                              </Button>
                            </div>
                            
                            {(() => {
                              const analysis = retentionAnalysis[volume.id]
                              if (!analysis) {
                                return (
                                  <div className="flex items-center justify-center py-8">
                                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                                  </div>
                                )
                              }
                              return (
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                {/* Left column: Retention slider */}
                                <div className="space-y-4">
                                  <div>
                                    <Label className="text-sm font-medium">
                                      Días de retención: {analysis.current_retention_days}
                                    </Label>
                                    <div className="flex items-center gap-4 mt-2">
                                      <span className="text-xs text-muted-foreground">1</span>
                                      <Slider
                                        value={[analysis.current_retention_days]}
                                        onValueChange={(value) => {
                                          const newValue = value[0]
                                          if (newValue !== undefined) {
                                            setRetentionAnalysis(prev => ({
                                              ...prev,
                                              [volume.id]: { ...analysis, current_retention_days: newValue }
                                            }))
                                          }
                                        }}
                                        onValueCommit={(value) => {
                                          const newValue = value[0]
                                          if (newValue !== undefined) {
                                            handleUpdateRetention(volume.id, newValue)
                                          }
                                        }}
                                        min={1}
                                        max={90}
                                        step={1}
                                        className="flex-1"
                                        disabled={updatingRetention === volume.id}
                                      />
                                      <span className="text-xs text-muted-foreground">90</span>
                                    </div>
                                  </div>
                                  
                                  {/* Show warnings */}
                                  {analysis.warnings.map((warning, idx) => (
                                    <Alert key={idx} variant={warning.level === 'critical' ? 'destructive' : 'default'}>
                                      <AlertTriangle className="h-4 w-4" />
                                      <AlertDescription>
                                        {warning.message}
                                      </AlertDescription>
                                    </Alert>
                                  ))}
                                  
                                  {analysis.recommended_retention_days < 
                                   analysis.current_retention_days && (
                                    <Alert>
                                      <AlertCircle className="h-4 w-4" />
                                      <AlertDescription>
                                        Recomendado: <strong>{analysis.recommended_retention_days} días</strong> 
                                        {" "}según el espacio disponible
                                        <Button 
                                          variant="link" 
                                          size="sm" 
                                          className="ml-2 h-auto p-0"
                                          onClick={() => handleUpdateRetention(
                                            volume.id, 
                                            analysis.recommended_retention_days
                                          )}
                                        >
                                          Aplicar
                                        </Button>
                                      </AlertDescription>
                                    </Alert>
                                  )}
                                </div>
                                
                                {/* Right column: Statistics */}
                                <div className="grid grid-cols-2 gap-3 text-sm">
                                  <div className="p-3 bg-background rounded-lg border">
                                    <div className="text-muted-foreground">Espacio libre</div>
                                    <div className="font-medium text-lg">
                                      {formatBytes(analysis.storage.free_bytes)}
                                    </div>
                                    <div className="text-xs text-muted-foreground">
                                      {analysis.storage.free_percent.toFixed(1)}%
                                    </div>
                                  </div>
                                  <div className="p-3 bg-background rounded-lg border">
                                    <div className="text-muted-foreground">Cámaras activas</div>
                                    <div className="font-medium text-lg">
                                      {analysis.cameras.active_count}
                                    </div>
                                    <div className="text-xs text-muted-foreground">
                                      ~{analysis.cameras.estimated_gb_per_camera_per_day} GB/día c/u
                                    </div>
                                  </div>
                                  <div className="p-3 bg-background rounded-lg border">
                                    <div className="text-muted-foreground">Grabación más antigua</div>
                                    <div className="font-medium text-lg">
                                      {analysis.recordings.oldest_days} días
                                    </div>
                                    <div className="text-xs text-muted-foreground">
                                      {formatBytes(analysis.recordings.total_bytes)} total
                                    </div>
                                  </div>
                                  <div className="p-3 bg-background rounded-lg border">
                                    <div className="text-muted-foreground">Retención recomendada</div>
                                    <div className={`font-medium text-lg ${
                                      analysis.recommended_retention_days < 
                                      analysis.current_retention_days 
                                        ? 'text-yellow-600' 
                                        : 'text-green-600'
                                    }`}>
                                      {analysis.recommended_retention_days} días
                                    </div>
                                    <div className="text-xs text-muted-foreground">
                                      {analysis.can_increase_retention ? 'Puede aumentar' : 'Espacio limitado'}
                                    </div>
                                  </div>
                                </div>
                              </div>
                              )
                            })()}
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      
      {/* Info Box */}
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Nota sobre el montaje de volúmenes</AlertTitle>
        <AlertDescription>
          Para usar NAS o dispositivos USB, necesitas configurar los montajes en el sistema host 
          y actualizar el <code className="bg-muted px-1 rounded">docker-compose.yml</code> para 
          incluir los volúmenes adicionales. Los volúmenes cloud (S3, Azure) requieren configuración 
          adicional usando herramientas como <code className="bg-muted px-1 rounded">s3fs</code> o 
          <code className="bg-muted px-1 rounded">rclone</code>.
        </AlertDescription>
      </Alert>
    </div>
  )
}
