"use client"

import { useState, useEffect } from "react"
import { VideoPlayer } from "./video-player"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "./ui/card"
import { RefreshCw, Video, VideoOff } from "lucide-react"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"

interface Camera {
  id: number
  name: string
  rtsp_url: string
  is_active: boolean
}

export const LiveViewGrid = () => {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedCamera, setSelectedCamera] = useState<Camera | null>(null)

  const fetchCameras = async () => {
    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/api/cameras`)
      if (response.ok) {
        const data = await response.json()
        setCameras(data)
        // Auto-select first camera if none selected
        if (data.length > 0 && !selectedCamera) {
          setSelectedCamera(data[0])
        }
      }
    } catch (error) {
      console.error("Failed to fetch cameras", error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCameras()
  }, [])

  const sanitizePathName = (name: string): string => {
    return name.replace(/\s+/g, '_').replace(/[^a-zA-Z0-9_-]/g, '').toLowerCase()
  }

  const getHLSUrl = (cameraName: string) => {
    const streamName = sanitizePathName(cameraName)
    return `http://localhost:8888/${streamName}/index.m3u8`
  }

  if (loading && cameras.length === 0) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center text-muted-foreground">
          <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-2" />
          <p>Loading cameras...</p>
        </div>
      </div>
    )
  }

  if (cameras.length === 0) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center text-muted-foreground">
          <VideoOff className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p className="text-lg font-medium">No cameras found</p>
          <p className="text-sm">Add a camera in Settings to get started.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Main viewer - large video player */}
      <div className="flex-1 min-h-0">
        <Card className="h-full bg-black/5 dark:bg-white/5">
          <CardContent className="p-4 h-full flex flex-col">
            {selectedCamera ? (
              <>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Video className="h-4 w-4 text-green-500" />
                    <span className="font-medium">{selectedCamera.name}</span>
                    <span className="text-xs text-muted-foreground">• Live</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={fetchCameras}
                    disabled={loading}
                  >
                    <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                  </Button>
                </div>
                <div className="flex-1 min-h-0 rounded-lg overflow-hidden bg-black flex items-center justify-center">
                  <div className="w-full max-w-4xl">
                    <VideoPlayer 
                      key={selectedCamera.id}
                      src={getHLSUrl(selectedCamera.name)} 
                    />
                  </div>
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-muted-foreground">
                <p>Select a camera to view</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Camera thumbnails - horizontal scroll */}
      <div className="shrink-0">
        <div className="flex gap-3 overflow-x-auto pb-2">
          {cameras.map((camera) => (
            <button
              key={camera.id}
              onClick={() => setSelectedCamera(camera)}
              className={`shrink-0 group relative rounded-lg overflow-hidden transition-all ${
                selectedCamera?.id === camera.id
                  ? 'ring-2 ring-primary ring-offset-2'
                  : 'hover:ring-2 hover:ring-muted-foreground/50 hover:ring-offset-1'
              }`}
            >
              <Card className="w-40 h-24 bg-gray-900">
                <CardContent className="p-0 h-full relative">
                  {/* Thumbnail preview - shows a static frame or icon */}
                  <div className="absolute inset-0 flex items-center justify-center bg-linear-to-t from-black/60 to-transparent">
                    <Video className="h-6 w-6 text-white/70" />
                  </div>
                  {/* Camera name overlay */}
                  <div className="absolute bottom-0 left-0 right-0 p-2 bg-linear-to-t from-black/80 to-transparent">
                    <p className="text-xs font-medium text-white truncate">
                      {camera.name}
                    </p>
                    <div className="flex items-center gap-1">
                      <span className={`w-1.5 h-1.5 rounded-full ${camera.is_active ? 'bg-green-500' : 'bg-red-500'}`} />
                      <span className="text-[10px] text-white/70">
                        {camera.is_active ? 'Online' : 'Offline'}
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
