"use client"

import { useCameras } from "@/contexts/camera-context"
import { VideoPlayer } from "@/components/video-player"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Video, VideoOff, RefreshCw } from "lucide-react"

export function CameraViewer() {
  const { selectedCamera, loading, refreshCameras, cameras } = useCameras()

  const sanitizePathName = (name: string): string => {
    return name.replace(/\s+/g, "_").replace(/[^a-zA-Z0-9_-]/g, "").toLowerCase()
  }

  const getHLSUrl = (cameraName: string) => {
    const streamName = sanitizePathName(cameraName)
    const streamUrl = process.env.NEXT_PUBLIC_STREAM_URL || 'http://localhost:8888'
    return `${streamUrl}/${streamName}/index.m3u8`
  }

  // Loading state
  if (loading && cameras.length === 0) {
    return (
      <Card className="h-full bg-black/5 dark:bg-white/5 flex items-center justify-center">
        <div className="text-center text-muted-foreground">
          <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-2" />
          <p>Loading cameras...</p>
        </div>
      </Card>
    )
  }

  // No cameras available
  if (cameras.length === 0) {
    return (
      <Card className="h-full bg-black/5 dark:bg-white/5 flex items-center justify-center">
        <div className="text-center text-muted-foreground">
          <VideoOff className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p className="text-lg font-medium">No cameras found</p>
          <p className="text-sm">Add a camera in Settings to get started.</p>
        </div>
      </Card>
    )
  }

  // No camera selected (shouldn't happen if auto-select works)
  if (!selectedCamera) {
    return (
      <Card className="h-full bg-black/5 dark:bg-white/5 flex items-center justify-center">
        <div className="text-center text-muted-foreground">
          <Video className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p className="text-lg font-medium">Select a camera</p>
          <p className="text-sm">Click on a camera above to view the live feed.</p>
        </div>
      </Card>
    )
  }

  // Camera selected - show stream
  return (
    <Card className="h-full bg-black/5 dark:bg-white/5 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b shrink-0">
        <div className="flex items-center gap-2">
          <Video className="h-4 w-4 text-green-500" />
          <span className="font-medium">{selectedCamera.name}</span>
          <span className="text-xs text-muted-foreground">• Live</span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={refreshCameras}
          disabled={loading}
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </Button>
      </div>

      {/* Video Player */}
      <div className="flex-1 min-h-0 bg-black">
        <VideoPlayer
          key={selectedCamera.id}
          src={getHLSUrl(selectedCamera.name)}
        />
      </div>
    </Card>
  )
}
