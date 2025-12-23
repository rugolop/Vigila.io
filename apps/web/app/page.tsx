import { CameraGrid } from "@/components/camera-grid"
import { CameraViewer } from "@/components/camera-viewer"

export default function Page() {
  return (
    <div className="flex flex-col h-full p-4 gap-4">
      {/* Camera thumbnails grid */}
      <div className="shrink-0">
        <CameraGrid />
      </div>
      
      {/* Main video viewer */}
      <div className="flex-1 min-h-0">
        <CameraViewer />
      </div>
    </div>
  )
}

