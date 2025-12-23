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

interface Camera {
  id: number
  name: string
  rtsp_url: string
  is_active: boolean
  stream_mode?: string
  created_at: string
}

export const CameraList = () => {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [newCameraName, setNewCameraName] = useState("")
  const [newCameraUrl, setNewCameraUrl] = useState("")
  const [loading, setLoading] = useState(false)

  const fetchCameras = useCallback(async () => {
    try {
      const response = await fetch("http://localhost:8001/cameras/")
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
    if (!confirm("¿Estás seguro de que quieres eliminar esta cámara?")) {
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
          <form onSubmit={handleAddCamera} className="grid gap-4 md:grid-cols-3 items-end">
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
            <Button type="submit" disabled={loading}>
              {loading ? "Añadiendo..." : "Añadir Cámara"}
            </Button>
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
                <TableHead>URL RTSP</TableHead>
                <TableHead>Modo</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {cameras.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                    No hay cámaras configuradas. Añade una cámara manualmente o usa el descubrimiento de red.
                  </TableCell>
                </TableRow>
              ) : (
                cameras.map((camera) => (
                  <TableRow key={camera.id}>
                    <TableCell className="font-mono">{camera.id}</TableCell>
                    <TableCell className="font-medium">{camera.name}</TableCell>
                    <TableCell className="font-mono text-xs max-w-[200px] truncate">{camera.rtsp_url}</TableCell>
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
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => handleDeleteCamera(camera.id)}
                      >
                        Eliminar
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
