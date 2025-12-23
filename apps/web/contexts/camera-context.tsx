"use client"

import { createContext, useContext, useState, useEffect, ReactNode } from "react"

interface Camera {
  id: number
  name: string
  rtsp_url: string
  is_active: boolean
}

interface CameraContextType {
  cameras: Camera[]
  selectedCamera: Camera | null
  setSelectedCamera: (camera: Camera | null) => void
  loading: boolean
  refreshCameras: () => Promise<void>
}

const CameraContext = createContext<CameraContextType | undefined>(undefined)

export function CameraProvider({ children }: { children: ReactNode }) {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [selectedCamera, setSelectedCamera] = useState<Camera | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchCameras = async () => {
    setLoading(true)
    try {
      const response = await fetch("http://localhost:8001/cameras/")
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

  return (
    <CameraContext.Provider
      value={{
        cameras,
        selectedCamera,
        setSelectedCamera,
        loading,
        refreshCameras: fetchCameras,
      }}
    >
      {children}
    </CameraContext.Provider>
  )
}

export function useCameras() {
  const context = useContext(CameraContext)
  if (context === undefined) {
    throw new Error("useCameras must be used within a CameraProvider")
  }
  return context
}
