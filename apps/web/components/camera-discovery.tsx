"use client"

import { useState } from "react"
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
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

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

export const CameraDiscovery = () => {
  const [discoveredCameras, setDiscoveredCameras] = useState<DiscoveredCamera[]>([])
  const [discovering, setDiscovering] = useState(false)
  const [networkRange, setNetworkRange] = useState("192.168.1.0/24")
  const [addingCamera, setAddingCamera] = useState<string | null>(null)
  const [selectedUrls, setSelectedUrls] = useState<Record<string, string>>({})
  const [useOnvif, setUseOnvif] = useState(true)
  const [usePortScan, setUsePortScan] = useState(true)

  const discoverCameras = async () => {
    setDiscovering(true)
    setDiscoveredCameras([])
    try {
      const response = await fetch(
        `http://localhost:8001/cameras/discover?use_onvif=${useOnvif}&use_port_scan=${usePortScan}&network_range=${encodeURIComponent(networkRange)}`,
        { method: "POST" }
      )
      if (response.ok) {
        const data = await response.json()
        const cameras = data.cameras || []
        setDiscoveredCameras(cameras)
        // Set default selected URLs
        const defaults: Record<string, string> = {}
        cameras.forEach((cam: DiscoveredCamera) => {
          if (cam.rtsp_urls.length > 0 && cam.rtsp_urls[0]) {
            defaults[cam.ip] = cam.rtsp_urls[0]
          }
        })
        setSelectedUrls(defaults)
      }
    } catch (error) {
      console.error("Failed to discover cameras", error)
    } finally {
      setDiscovering(false)
    }
  }

  const addDiscoveredCamera = async (camera: DiscoveredCamera) => {
    const rtspUrl = selectedUrls[camera.ip]
    if (!rtspUrl) return

    setAddingCamera(camera.ip)
    try {
      const cameraName = camera.name || camera.manufacturer 
        ? `${camera.manufacturer || "Camera"} ${camera.model || ""} (${camera.ip.split('.').pop()})`
        : `Cámara ${camera.ip.split('.').pop()}`
      
      const response = await fetch("http://localhost:8001/cameras/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: cameraName.trim(),
          rtsp_url: rtspUrl,
          is_active: true,
        }),
      })

      if (response.ok) {
        // Remove from discovered list
        setDiscoveredCameras(prev => prev.filter(c => c.ip !== camera.ip))
      }
    } catch (error) {
      console.error("Failed to add discovered camera", error)
    } finally {
      setAddingCamera(null)
    }
  }

  const addAllCameras = async () => {
    for (const camera of discoveredCameras) {
      if (selectedUrls[camera.ip]) {
        await addDiscoveredCamera(camera)
      }
    }
  }

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"/>
              <path d="M12 6v6l4 2"/>
            </svg>
            Descubrimiento de Cámaras
          </CardTitle>
          <CardDescription>
            Escanea tu red local para encontrar cámaras IP automáticamente usando ONVIF y escaneo de puertos
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Discovery Options */}
          <div className="grid gap-4 md:grid-cols-4 items-end">
            <div className="grid gap-2">
              <Label htmlFor="network">Rango de Red (CIDR)</Label>
              <Input
                id="network"
                placeholder="192.168.1.0/24"
                value={networkRange}
                onChange={(e) => setNetworkRange(e.target.value)}
              />
            </div>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={useOnvif}
                  onChange={(e) => setUseOnvif(e.target.checked)}
                  className="w-4 h-4 rounded border-gray-300"
                />
                <span className="text-sm">ONVIF</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={usePortScan}
                  onChange={(e) => setUsePortScan(e.target.checked)}
                  className="w-4 h-4 rounded border-gray-300"
                />
                <span className="text-sm">Port Scan</span>
              </label>
            </div>
            <Button onClick={discoverCameras} disabled={discovering || (!useOnvif && !usePortScan)}>
              {discovering ? (
                <>
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Escaneando...
                </>
              ) : (
                <>
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="11" cy="11" r="8"/>
                    <path d="m21 21-4.35-4.35"/>
                  </svg>
                  Escanear Red
                </>
              )}
            </Button>
            {discoveredCameras.length > 0 && (
              <Button variant="outline" onClick={addAllCameras}>
                Añadir Todas ({discoveredCameras.length})
              </Button>
            )}
          </div>

          {/* Discovered Cameras Table */}
          {discoveredCameras.length > 0 ? (
            <div className="border rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>IP</TableHead>
                    <TableHead>Puerto</TableHead>
                    <TableHead>Fabricante</TableHead>
                    <TableHead>Modelo</TableHead>
                    <TableHead>Método</TableHead>
                    <TableHead>Stream RTSP</TableHead>
                    <TableHead className="text-right">Acción</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {discoveredCameras.map((camera) => (
                    <TableRow key={camera.ip}>
                      <TableCell className="font-mono">{camera.ip}</TableCell>
                      <TableCell>{camera.port}</TableCell>
                      <TableCell>{camera.manufacturer || "Desconocido"}</TableCell>
                      <TableCell>{camera.model || "-"}</TableCell>
                      <TableCell>
                        <Badge variant={camera.discovery_method === "onvif" ? "default" : "secondary"}>
                          {camera.discovery_method === "onvif" ? "ONVIF" : "Port Scan"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {camera.rtsp_urls.length > 1 ? (
                          <Select 
                            value={selectedUrls[camera.ip] || camera.rtsp_urls[0]}
                            onValueChange={(value) => setSelectedUrls(prev => ({ ...prev, [camera.ip]: value }))}
                          >
                            <SelectTrigger className="w-[200px] text-xs">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {camera.rtsp_urls.map((url, i) => (
                                <SelectItem key={i} value={url} className="text-xs">
                                  {url.replace(`rtsp://${camera.ip}:${camera.port}`, '')}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        ) : (
                          <span className="text-xs font-mono">
                            {camera.rtsp_urls[0]?.replace(`rtsp://${camera.ip}:${camera.port}`, '') || "N/A"}
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          disabled={addingCamera === camera.ip || !selectedUrls[camera.ip]}
                          onClick={() => addDiscoveredCamera(camera)}
                        >
                          {addingCamera === camera.ip ? (
                            <>
                              <svg className="animate-spin -ml-1 mr-1 h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                              </svg>
                              Añadiendo
                            </>
                          ) : (
                            "Añadir"
                          )}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="text-center py-12 border rounded-lg bg-muted/50">
              {discovering ? (
                <div className="space-y-3">
                  <svg className="animate-spin mx-auto h-8 w-8 text-muted-foreground" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <p className="text-muted-foreground">Buscando cámaras en la red...</p>
                  <p className="text-xs text-muted-foreground">Esto puede tardar unos segundos</p>
                </div>
              ) : (
                <div className="space-y-3">
                  <svg xmlns="http://www.w3.org/2000/svg" className="mx-auto h-12 w-12 text-muted-foreground/50" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
                    <circle cx="12" cy="13" r="4"/>
                  </svg>
                  <p className="text-muted-foreground">No se han encontrado cámaras</p>
                  <p className="text-xs text-muted-foreground">
                    Haz clic en &quot;Escanear Red&quot; para buscar cámaras en tu red local
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Help Section */}
          <div className="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-900 rounded-lg p-4">
            <h4 className="text-sm font-medium text-blue-800 dark:text-blue-300 mb-2">
              💡 Consejos para el descubrimiento
            </h4>
            <ul className="text-xs text-blue-700 dark:text-blue-400 space-y-1">
              <li>• <strong>ONVIF</strong>: Detecta cámaras compatibles con el protocolo ONVIF (la mayoría de cámaras IP modernas)</li>
              <li>• <strong>Port Scan</strong>: Busca puertos RTSP comunes (554, 8554) en dispositivos de la red</li>
              <li>• Asegúrate de que el rango de red corresponde a tu red local (ej: 192.168.1.0/24)</li>
              <li>• Algunas cámaras pueden requerir credenciales para acceder al stream RTSP</li>
            </ul>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
