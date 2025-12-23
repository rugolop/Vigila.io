"use client"

import { useState, useEffect } from "react"
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

interface Camera {
  id: number
  name: string
  rtsp_url: string
  is_active: boolean
  stream_mode?: string
  created_at: string
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

export const CameraManager = () => {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [newCameraName, setNewCameraName] = useState("")
  const [newCameraUrl, setNewCameraUrl] = useState("")
  const [loading, setLoading] = useState(false)
  
  // Discovery state
  const [discoveredCameras, setDiscoveredCameras] = useState<DiscoveredCamera[]>([])
  const [discovering, setDiscovering] = useState(false)
  const [networkRange, setNetworkRange] = useState("192.168.1.0/24")
  const [addingCamera, setAddingCamera] = useState<string | null>(null)

  const fetchCameras = async () => {
    try {
      const response = await fetch("http://localhost:8001/cameras/")
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
        `http://localhost:8001/cameras/discover?use_onvif=true&use_port_scan=true&network_range=${encodeURIComponent(networkRange)}`,
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

  const addDiscoveredCamera = async (camera: DiscoveredCamera, rtspUrl: string) => {
    setAddingCamera(camera.ip)
    try {
      const cameraName = camera.name || camera.manufacturer 
        ? `${camera.manufacturer || "Camera"} ${camera.ip.split('.').pop()}`
        : `Camera ${camera.ip.split('.').pop()}`
      
      const response = await fetch("http://localhost:8001/cameras/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: cameraName,
          rtsp_url: rtspUrl,
          is_active: true,
        }),
      })

      if (response.ok) {
        fetchCameras()
        // Remove from discovered list
        setDiscoveredCameras(prev => prev.filter(c => c.ip !== camera.ip))
      }
    } catch (error) {
      console.error("Failed to add discovered camera", error)
    } finally {
      setAddingCamera(null)
    }
  }

  const handleAddCamera = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      const response = await fetch("http://localhost:8001/cameras/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: newCameraName,
          rtsp_url: newCameraUrl,
          is_active: true,
        }),
      })

      if (response.ok) {
        setNewCameraName("")
        setNewCameraUrl("")
        fetchCameras()
      }
    } catch (error) {
      console.error("Failed to add camera", error)
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteCamera = async (cameraId: number) => {
    if (!confirm("Are you sure you want to delete this camera?")) {
      return
    }

    try {
      const response = await fetch(`http://localhost:8001/cameras/${cameraId}`, {
        method: "DELETE",
      })

      if (response.ok) {
        fetchCameras()
      }
    } catch (error) {
      console.error("Failed to delete camera", error)
    }
  }

  useEffect(() => {
    fetchCameras()
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
            Discover Cameras
          </CardTitle>
          <CardDescription>
            Scan your local network to automatically find IP cameras
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4 items-end mb-4">
            <div className="grid gap-2 flex-1">
              <Label htmlFor="network">Network Range (CIDR)</Label>
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
                  Scanning...
                </>
              ) : (
                "Scan Network"
              )}
            </Button>
          </div>

          {discoveredCameras.length > 0 && (
            <div className="border rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>IP Address</TableHead>
                    <TableHead>Port</TableHead>
                    <TableHead>Manufacturer</TableHead>
                    <TableHead>Method</TableHead>
                    <TableHead>RTSP URL</TableHead>
                    <TableHead>Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {discoveredCameras.map((camera) => (
                    <TableRow key={camera.ip}>
                      <TableCell className="font-mono">{camera.ip}</TableCell>
                      <TableCell>{camera.port}</TableCell>
                      <TableCell>{camera.manufacturer || "Unknown"}</TableCell>
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
                            addDiscoveredCamera(camera, select.value)
                          }}
                        >
                          {addingCamera === camera.ip ? "Adding..." : "Add"}
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
              Click "Scan Network" to discover cameras on your network
            </p>
          )}
        </CardContent>
      </Card>

      {/* Manual Add Section */}
      <Card>
        <CardHeader>
          <CardTitle>Add Camera Manually</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAddCamera} className="grid gap-4 md:grid-cols-3 items-end">
            <div className="grid gap-2">
              <Label htmlFor="name">Camera Name</Label>
              <Input
                id="name"
                placeholder="e.g. Front Door"
                value={newCameraName}
                onChange={(e) => setNewCameraName(e.target.value)}
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="url">RTSP URL</Label>
              <Input
                id="url"
                placeholder="rtsp://..."
                value={newCameraUrl}
                onChange={(e) => setNewCameraUrl(e.target.value)}
                required
              />
            </div>
            <Button type="submit" disabled={loading}>
              {loading ? "Adding..." : "Add Camera"}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Connected Cameras</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>RTSP URL</TableHead>
                <TableHead>Mode</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {cameras.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-gray-500">
                    No cameras found.
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
                        {camera.is_active ? "Active" : "Inactive"}
                      </span>
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => handleDeleteCamera(camera.id)}
                      >
                        Delete
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
