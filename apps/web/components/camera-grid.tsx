"use client"

import { useCameras } from "@/contexts/camera-context"
import { Card, CardContent } from "@/components/ui/card"
import { Video, RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"

export function CameraGrid() {
  const { cameras, selectedCamera, setSelectedCamera, loading, refreshCameras } = useCameras()

  if (loading && cameras.length === 0) {
    return (
      <div className="grid auto-rows-min gap-3 grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div
            key={i}
            className="aspect-video rounded-lg bg-muted/50 animate-pulse"
          />
        ))}
      </div>
    )
  }

  if (cameras.length === 0) {
    return (
      <div className="flex items-center justify-center py-8 text-muted-foreground">
        <p className="text-sm">No cameras available. Add cameras in Settings.</p>
      </div>
    )
  }

  return (
    <div className="grid auto-rows-min gap-3 grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
      {cameras.map((camera) => (
        <button
          key={camera.id}
          onClick={() => setSelectedCamera(camera)}
          className={cn(
            "group relative aspect-video rounded-lg overflow-hidden transition-all",
            "hover:ring-2 hover:ring-primary/50 hover:ring-offset-1",
            selectedCamera?.id === camera.id && "ring-2 ring-primary ring-offset-2"
          )}
        >
          <Card className="h-full w-full bg-gray-900 border-0">
            <CardContent className="p-0 h-full relative">
              {/* Camera preview background */}
              <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-t from-black/70 to-black/30">
                <Video className="h-5 w-5 text-white/60" />
              </div>
              
              {/* Camera info overlay */}
              <div className="absolute bottom-0 left-0 right-0 p-1.5 bg-gradient-to-t from-black/90 to-transparent">
                <p className="text-[10px] font-medium text-white truncate">
                  {camera.name}
                </p>
                <div className="flex items-center gap-1">
                  <span
                    className={cn(
                      "w-1.5 h-1.5 rounded-full",
                      camera.is_active ? "bg-green-500" : "bg-red-500"
                    )}
                  />
                  <span className="text-[8px] text-white/70">
                    {camera.is_active ? "Online" : "Offline"}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        </button>
      ))}
    </div>
  )
}
