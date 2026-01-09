"use client"

import { useEffect, useState, useCallback } from "react"
import { useTenant } from "@/hooks/use-tenant"
import { RequireAdmin, AccessDenied } from "@/components/access-control"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { 
  Wifi, 
  WifiOff, 
  Trash2, 
  RefreshCw, 
  Camera, 
  Plus, 
  Copy, 
  Check,
  Server,
  Search,
  Eye,
  MonitorPlay,
  Download
} from "lucide-react"
import { formatDistanceToNow } from "date-fns"
import { es } from "date-fns/locale"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"

interface Agent {
  agent_id: string
  name: string
  tenant_id: number
  tenant_slug: string
  local_ip: string
  version: string
  is_online: boolean
  last_seen: string
  cameras_count: number
}

interface DiscoveredCamera {
  ip: string
  port: number
  manufacturer: string
  model: string
  name: string
  rtsp_url: string | null
  onvif_url: string | null
}

interface Tenant {
  id: number
  name: string
  slug: string
}

export default function AgentsPage() {
  const { tenantId, isSuperAdmin, loading: tenantLoading } = useTenant()
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [selectedTenant, setSelectedTenant] = useState<string>("all")
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  const [discoveredCameras, setDiscoveredCameras] = useState<DiscoveredCamera[]>([])
  const [loadingCameras, setLoadingCameras] = useState(false)
  const [showDownloadDialog, setShowDownloadDialog] = useState(false)
  const [agentName, setAgentName] = useState("vigila-agent")
  const [downloading, setDownloading] = useState(false)
  const [downloadTenantId, setDownloadTenantId] = useState<string>("")

  // Fetch agents
  const fetchAgents = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      
      // Build URL with tenant filter
      let url = `${API_URL}/api/agents`
      
      if (!isSuperAdmin && tenantId) {
        // Regular admin: filter by their tenant
        url += `?tenant_id=${tenantId}`
      } else if (isSuperAdmin && selectedTenant !== "all") {
        // Super admin with filter
        url += `?tenant_id=${selectedTenant}`
      }
      
      const response = await fetch(url)
      if (!response.ok) throw new Error("Error al cargar agentes")
      
      const data = await response.json()
      setAgents(data.agents || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error desconocido")
    } finally {
      setLoading(false)
    }
  }, [tenantId, isSuperAdmin, selectedTenant])

  // Fetch tenants for super admin
  const fetchTenants = useCallback(async () => {
    if (!isSuperAdmin) return
    
    try {
      const response = await fetch(`${API_URL}/api/tenants`)
      if (response.ok) {
        const data = await response.json()
        setTenants(data || [])
      }
    } catch (err) {
      console.error("Error fetching tenants:", err)
    }
  }, [isSuperAdmin])

  useEffect(() => {
    if (!tenantLoading) {
      fetchAgents()
      fetchTenants()
    }
  }, [tenantLoading, fetchAgents, fetchTenants])

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(fetchAgents, 30000)
    return () => clearInterval(interval)
  }, [fetchAgents])

  // Download agent package
  const downloadAgent = async () => {
    // Para super admin, usar downloadTenantId; para admin normal, usar su tenantId
    const targetTenantId = isSuperAdmin 
      ? (downloadTenantId ? parseInt(downloadTenantId) : null)
      : tenantId
    
    if (!targetTenantId) {
      setError("Selecciona un tenant primero")
      return
    }
    
    setDownloading(true)
    
    try {
      const response = await fetch(`${API_URL}/api/agents/download`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          tenant_id: targetTenantId,
          agent_name: agentName
        })
      })
      
      if (!response.ok) throw new Error("Error al generar el agente")
      
      // Download the file
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `vigila-agent.zip`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      
      setShowDownloadDialog(false)
      setAgentName("vigila-agent")
      setDownloadTenantId("")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error desconocido")
    } finally {
      setDownloading(false)
    }
  }

  // Delete agent
  const deleteAgent = async (agentId: string) => {
    if (!confirm("¿Estás seguro de eliminar este agente?")) return
    
    try {
      const response = await fetch(`${API_URL}/api/agents/${agentId}`, {
        method: "DELETE"
      })
      
      if (!response.ok) throw new Error("Error al eliminar agente")
      
      fetchAgents()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error desconocido")
    }
  }

  // Trigger discovery on agent
  const triggerDiscovery = async (agentId: string) => {
    try {
      const response = await fetch(`${API_URL}/api/agents/${agentId}/discover`, {
        method: "POST"
      })
      
      if (!response.ok) throw new Error("Error al iniciar descubrimiento")
      
      // Feedback to user
      alert("Comando de descubrimiento enviado. Las cámaras aparecerán en breve.")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error desconocido")
    }
  }

  // View discovered cameras
  const viewDiscoveredCameras = async (agent: Agent) => {
    setSelectedAgent(agent)
    setLoadingCameras(true)
    
    try {
      const response = await fetch(`${API_URL}/api/agents/${agent.agent_id}/discovered`)
      if (response.ok) {
        const data = await response.json()
        setDiscoveredCameras(data.cameras || [])
      }
    } catch (err) {
      console.error("Error fetching cameras:", err)
    } finally {
      setLoadingCameras(false)
    }
  }

  if (tenantLoading) {
    return (
      <div className="container mx-auto py-6">
        <Skeleton className="h-8 w-48 mb-6" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  return (
    <RequireAdmin showAccessDenied>
      <div className="container mx-auto py-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Agentes Locales</h1>
            <p className="text-muted-foreground">
              Gestiona los agentes instalados en redes locales para conectar cámaras remotas
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="icon" onClick={fetchAgents}>
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button onClick={() => setShowDownloadDialog(true)}>
              <Download className="h-4 w-4 mr-2" />
              Descargar Agente
            </Button>
          </div>
        </div>

        {/* Tenant Filter (Super Admin Only) */}
        {isSuperAdmin && tenants.length > 0 && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Filtrar por Tenant</CardTitle>
            </CardHeader>
            <CardContent>
              <Select value={selectedTenant} onValueChange={setSelectedTenant}>
                <SelectTrigger className="w-[300px]">
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
            </CardContent>
          </Card>
        )}

        {/* Stats Cards */}
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Agentes</CardTitle>
              <Server className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{agents.length}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">En Línea</CardTitle>
              <Wifi className="h-4 w-4 text-green-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">
                {agents.filter(a => a.is_online).length}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Cámaras Conectadas</CardTitle>
              <Camera className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {agents.reduce((sum, a) => sum + a.cameras_count, 0)}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Error Message */}
        {error && (
          <Card className="border-destructive">
            <CardContent className="pt-6">
              <p className="text-destructive">{error}</p>
            </CardContent>
          </Card>
        )}

        {/* Agents Table */}
        <Card>
          <CardHeader>
            <CardTitle>Agentes Registrados</CardTitle>
            <CardDescription>
              Lista de agentes locales conectados al sistema
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-2">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : agents.length === 0 ? (
              <div className="text-center py-12">
                <Server className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <h3 className="text-lg font-medium mb-2">No hay agentes registrados</h3>
                <p className="text-muted-foreground mb-4">
                  Descarga e instala el agente en tu red local para conectar cámaras
                </p>
                <Button onClick={() => setShowDownloadDialog(true)}>
                  <Download className="h-4 w-4 mr-2" />
                  Descargar Primer Agente
                </Button>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Estado</TableHead>
                    <TableHead>Nombre</TableHead>
                    {isSuperAdmin && <TableHead>Tenant</TableHead>}
                    <TableHead>IP Local</TableHead>
                    <TableHead>Versión</TableHead>
                    <TableHead>Cámaras</TableHead>
                    <TableHead>Última Conexión</TableHead>
                    <TableHead className="text-right">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {agents.map((agent) => (
                    <TableRow key={agent.agent_id}>
                      <TableCell>
                        {agent.is_online ? (
                          <Badge variant="default" className="bg-green-500">
                            <Wifi className="h-3 w-3 mr-1" />
                            En Línea
                          </Badge>
                        ) : (
                          <Badge variant="secondary">
                            <WifiOff className="h-3 w-3 mr-1" />
                            Desconectado
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="font-medium">{agent.name}</TableCell>
                      {isSuperAdmin && (
                        <TableCell>
                          <Badge variant="outline">{agent.tenant_slug}</Badge>
                        </TableCell>
                      )}
                      <TableCell className="font-mono text-sm">{agent.local_ip}</TableCell>
                      <TableCell>{agent.version}</TableCell>
                      <TableCell>
                        <Badge variant="outline">
                          <Camera className="h-3 w-3 mr-1" />
                          {agent.cameras_count}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {formatDistanceToNow(new Date(agent.last_seen), { 
                          addSuffix: true, 
                          locale: es 
                        })}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button 
                            variant="ghost" 
                            size="icon"
                            onClick={() => triggerDiscovery(agent.agent_id)}
                            title="Buscar cámaras"
                          >
                            <Search className="h-4 w-4" />
                          </Button>
                          <Button 
                            variant="ghost" 
                            size="icon"
                            onClick={() => viewDiscoveredCameras(agent)}
                            title="Ver cámaras descubiertas"
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button 
                            variant="ghost" 
                            size="icon"
                            onClick={() => deleteAgent(agent.agent_id)}
                            title="Eliminar agente"
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Discovered Cameras Dialog */}
        <Dialog open={!!selectedAgent} onOpenChange={() => setSelectedAgent(null)}>
          <DialogContent className="sm:max-w-[700px]">
            <DialogHeader>
              <DialogTitle>
                Cámaras Descubiertas - {selectedAgent?.name}
              </DialogTitle>
              <DialogDescription>
                Cámaras encontradas en la red local del agente
              </DialogDescription>
            </DialogHeader>
            <div className="max-h-[400px] overflow-y-auto">
              {loadingCameras ? (
                <div className="space-y-2">
                  <Skeleton className="h-16 w-full" />
                  <Skeleton className="h-16 w-full" />
                </div>
              ) : discoveredCameras.length === 0 ? (
                <div className="text-center py-8">
                  <Camera className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                  <p className="text-muted-foreground">
                    No se han descubierto cámaras aún. Haz clic en "Buscar cámaras" para iniciar.
                  </p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>IP</TableHead>
                      <TableHead>Fabricante</TableHead>
                      <TableHead>Modelo</TableHead>
                      <TableHead>Nombre</TableHead>
                      <TableHead className="text-right">Acciones</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {discoveredCameras.map((camera, idx) => (
                      <TableRow key={idx}>
                        <TableCell className="font-mono">{camera.ip}:{camera.port}</TableCell>
                        <TableCell>{camera.manufacturer}</TableCell>
                        <TableCell>{camera.model}</TableCell>
                        <TableCell>{camera.name || "-"}</TableCell>
                        <TableCell className="text-right">
                          <Button variant="outline" size="sm">
                            <MonitorPlay className="h-4 w-4 mr-1" />
                            Conectar
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </div>
            <DialogFooter>
              <Button 
                variant="outline" 
                onClick={() => selectedAgent && triggerDiscovery(selectedAgent.agent_id)}
              >
                <Search className="h-4 w-4 mr-2" />
                Buscar Cámaras
              </Button>
              <Button onClick={() => setSelectedAgent(null)}>Cerrar</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Download Agent Dialog */}
        <Dialog open={showDownloadDialog} onOpenChange={setShowDownloadDialog}>
          <DialogContent className="sm:max-w-150">
            <DialogHeader>
              <DialogTitle>Descargar Agente Local</DialogTitle>
              <DialogDescription>
                Descarga el agente pre-configurado para instalar en tu red local.
                El token se genera automáticamente.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 max-h-[60vh] overflow-y-auto">
              {isSuperAdmin && tenants.length > 0 && (
                <div className="space-y-2">
                  <Label htmlFor="download-tenant">Tenant *</Label>
                  <Select value={downloadTenantId} onValueChange={setDownloadTenantId}>
                    <SelectTrigger id="download-tenant">
                      <SelectValue placeholder="Selecciona un tenant" />
                    </SelectTrigger>
                    <SelectContent>
                      {tenants.map((tenant) => (
                        <SelectItem key={tenant.id} value={tenant.id.toString()}>
                          {tenant.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    Selecciona el tenant para el cual deseas generar el agente
                  </p>
                </div>
              )}
              <div className="space-y-2">
                <Label htmlFor="agent-name">Nombre del Agente</Label>
                <Input
                  id="agent-name"
                  placeholder="vigila-agent"
                  value={agentName}
                  onChange={(e) => setAgentName(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Este nombre identificará al agente en el dashboard
                </p>
              </div>
              
              {/* Contenido del paquete */}
              <div className="bg-muted p-4 rounded-lg text-sm">
                <p className="font-medium mb-2">📦 El paquete incluye:</p>
                <ul className="list-disc list-inside space-y-1 text-muted-foreground">
                  <li>Scripts del agente (Python)</li>
                  <li>Archivo .env pre-configurado con tu token</li>
                  <li>Scripts de instalación automática (Linux/Windows)</li>
                  <li>README con instrucciones detalladas</li>
                </ul>
              </div>
              
              {/* Pasos de instalación */}
              <div className="bg-green-50 dark:bg-green-950 p-4 rounded-lg text-sm">
                <p className="font-medium text-green-700 dark:text-green-300 mb-2">🚀 Instalación rápida:</p>
                <div className="space-y-2 text-green-600 dark:text-green-400">
                  <p className="font-medium">Linux/macOS:</p>
                  <code className="block bg-green-100 dark:bg-green-900 p-2 rounded text-xs">
                    unzip vigila-agent.zip && cd vigila-agent && chmod +x install.sh && ./install.sh
                  </code>
                  <p className="font-medium mt-3">Windows (PowerShell como Admin):</p>
                  <code className="block bg-green-100 dark:bg-green-900 p-2 rounded text-xs">
                    Expand-Archive vigila-agent.zip; cd vigila-agent; .\install.bat
                  </code>
                </div>
              </div>
              
              {/* Requisitos */}
              <div className="bg-blue-50 dark:bg-blue-950 p-4 rounded-lg text-sm">
                <p className="font-medium text-blue-700 dark:text-blue-300 mb-2">⚙️ Requisitos del sistema:</p>
                <ul className="list-disc list-inside space-y-1 text-blue-600 dark:text-blue-400">
                  <li>Python 3.9 o superior</li>
                  <li>FFmpeg (se instala automáticamente en Linux)</li>
                  <li>Conexión a Internet</li>
                  <li>Acceso a la red local de las cámaras</li>
                </ul>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => {
                setShowDownloadDialog(false)
                setDownloadTenantId("")
              }}>
                Cancelar
              </Button>
              <Button 
                onClick={downloadAgent} 
                disabled={downloading || (isSuperAdmin && !downloadTenantId)}
              >
                {downloading ? (
                  <>
                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                    Generando...
                  </>
                ) : (
                  <>
                    <Download className="h-4 w-4 mr-2" />
                    Descargar ZIP
                  </>
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </RequireAdmin>
  )
}
