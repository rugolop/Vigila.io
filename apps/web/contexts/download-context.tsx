"use client"

import { createContext, useContext, useState, useCallback, useRef, ReactNode } from "react"

interface DownloadState {
  isDownloading: boolean
  progress: number
  message: string
  itemCount: number
}

interface DownloadContextType {
  downloadState: DownloadState
  startDownload: (message: string, itemCount: number) => void
  updateProgress: (progress: number, message?: string) => void
  finishDownload: () => void
  cancelDownload: () => void
  downloadWithProgress: (
    url: string,
    options: RequestInit | undefined,
    filename: string,
    itemCount?: number
  ) => Promise<void>
}

const DownloadContext = createContext<DownloadContextType | undefined>(undefined)

export function DownloadProvider({ children }: { children: ReactNode }) {
  const [downloadState, setDownloadState] = useState<DownloadState>({
    isDownloading: false,
    progress: 0,
    message: "",
    itemCount: 0,
  })
  
  // Usar refs para mantener el estado de la descarga activa
  // Esto evita que la navegación cancele la descarga
  const abortControllerRef = useRef<AbortController | null>(null)
  const isDownloadingRef = useRef(false)

  const startDownload = useCallback((message: string, itemCount: number) => {
    isDownloadingRef.current = true
    setDownloadState({
      isDownloading: true,
      progress: 0,
      message,
      itemCount,
    })
  }, [])

  const updateProgress = useCallback((progress: number, message?: string) => {
    // Solo actualizar si hay una descarga activa
    if (!isDownloadingRef.current) return
    setDownloadState((prev) => ({
      ...prev,
      progress,
      ...(message && { message }),
    }))
  }, [])

  const finishDownload = useCallback(() => {
    // Pequeño delay antes de cerrar para mostrar 100%
    setTimeout(() => {
      isDownloadingRef.current = false
      abortControllerRef.current = null
      setDownloadState({
        isDownloading: false,
        progress: 0,
        message: "",
        itemCount: 0,
      })
    }, 500)
  }, [])

  const cancelDownload = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    isDownloadingRef.current = false
    setDownloadState({
      isDownloading: false,
      progress: 0,
      message: "",
      itemCount: 0,
    })
  }, [])

  const downloadWithProgress = useCallback(
    async (
      url: string,
      options: RequestInit | undefined,
      filename: string,
      itemCount: number = 1
    ) => {
      // Cancelar cualquier descarga anterior
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
      
      // Crear nuevo AbortController
      const abortController = new AbortController()
      abortControllerRef.current = abortController
      
      const initialMessage =
        itemCount > 1
          ? `Comprimiendo ${itemCount} grabaciones...`
          : "Comprimiendo grabación..."

      startDownload(initialMessage, itemCount)

      try {
        const response = await fetch(url, {
          ...options,
          signal: abortController.signal,
        })

        if (!response.ok) {
          throw new Error("Error en la descarga")
        }
        
        // Verificar si fue cancelada
        if (abortController.signal.aborted) {
          return
        }

        const contentLength = response.headers.get("content-length")
        const total = contentLength ? parseInt(contentLength, 10) : 0

        const reader = response.body?.getReader()
        if (!reader) throw new Error("No se pudo leer la respuesta")

        const chunks: Uint8Array[] = []
        let receivedLength = 0

        if (total > 0) {
          updateProgress(
            0,
            itemCount > 1
              ? `Descargando ${itemCount} grabaciones...`
              : "Descargando grabación..."
          )

          while (true) {
            // Verificar si fue cancelada
            if (abortController.signal.aborted) {
              reader.cancel()
              return
            }
            
            const { done, value } = await reader.read()
            if (done) break

            chunks.push(value)
            receivedLength += value.length
            const progress = Math.round((receivedLength / total) * 100)
            updateProgress(progress)
          }
        } else {
          // Sin content-length, simulamos progreso
          let simulatedProgress = 0
          const progressInterval = setInterval(() => {
            if (abortController.signal.aborted) {
              clearInterval(progressInterval)
              return
            }
            simulatedProgress = Math.min(simulatedProgress + 5, 90)
            updateProgress(simulatedProgress)
          }, 200)

          while (true) {
            if (abortController.signal.aborted) {
              clearInterval(progressInterval)
              reader.cancel()
              return
            }
            
            const { done, value } = await reader.read()
            if (done) break
            chunks.push(value)
            receivedLength += value.length
          }

          clearInterval(progressInterval)
        }

        // Verificar una última vez antes de completar
        if (abortController.signal.aborted) {
          return
        }

        updateProgress(100, "Preparando archivo...")

        // Combinar chunks y crear blob
        const allChunks = new Uint8Array(receivedLength)
        let position = 0
        for (const chunk of chunks) {
          allChunks.set(chunk, position)
          position += chunk.length
        }
        const blob = new Blob([allChunks])
        const blobUrl = window.URL.createObjectURL(blob)
        const link = document.createElement("a")
        link.href = blobUrl
        link.download = filename
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        window.URL.revokeObjectURL(blobUrl)

        finishDownload()
      } catch (error) {
        // Ignorar errores de abort
        if (error instanceof Error && error.name === "AbortError") {
          return
        }
        console.error("Download failed:", error)
        isDownloadingRef.current = false
        abortControllerRef.current = null
        setDownloadState({
          isDownloading: false,
          progress: 0,
          message: "",
          itemCount: 0,
        })
        throw error
      }
    },
    [startDownload, updateProgress, finishDownload]
  )

  return (
    <DownloadContext.Provider
      value={{
        downloadState,
        startDownload,
        updateProgress,
        finishDownload,
        cancelDownload,
        downloadWithProgress,
      }}
    >
      {children}
    </DownloadContext.Provider>
  )
}

export function useDownload() {
  const context = useContext(DownloadContext)
  if (context === undefined) {
    throw new Error("useDownload must be used within a DownloadProvider")
  }
  return context
}
