"use client"

import { useEffect, useState } from "react"
import { createPortal } from "react-dom"
import { useDownload } from "@/contexts/download-context"
import { Progress } from "@/components/ui/progress"
import { Spinner } from "@/components/ui/spinner"
import { FileArchive, Check } from "lucide-react"

function DownloadProgressContent() {
  const { downloadState } = useDownload()

  if (!downloadState.isDownloading) return null

  return (
    <div className="fixed bottom-4 right-4 z-[9999] w-80 bg-background border rounded-lg shadow-lg p-4 space-y-3 animate-in slide-in-from-bottom-5 duration-300">
      <div className="flex items-center gap-3">
        {downloadState.progress < 100 ? (
          <div className="flex-shrink-0 p-2 bg-primary/10 rounded-full">
            <Spinner className="h-5 w-5 text-primary" />
          </div>
        ) : (
          <div className="flex-shrink-0 p-2 bg-green-500/10 rounded-full">
            <Check className="h-5 w-5 text-green-500" />
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <FileArchive className="h-4 w-4 text-muted-foreground flex-shrink-0" />
            <p className="text-sm font-medium truncate">
              {downloadState.itemCount > 1
                ? `${downloadState.itemCount} grabaciones`
                : "1 grabación"}
            </p>
          </div>
          <p className="text-xs text-muted-foreground truncate">
            {downloadState.message}
          </p>
        </div>
        <span className="text-sm font-medium tabular-nums">
          {downloadState.progress}%
        </span>
      </div>
      <Progress value={downloadState.progress} className="h-1.5" />
    </div>
  )
}

export function DownloadProgress() {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  // Usar portal para renderizar directamente en el body
  // Esto asegura que el componente no se desmonte durante la navegación
  if (!mounted) return null

  return createPortal(
    <DownloadProgressContent />,
    document.body
  )
}
