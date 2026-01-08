"use client"

import { useState, useEffect, useMemo } from "react"
import { format } from "date-fns"
import { es } from "date-fns/locale"
import { CalendarIcon, Download, Trash2, Play, ArrowUpDown, Search, ChevronLeft, ChevronRight, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Calendar } from "@/components/ui/calendar"
import { VideoPlayer } from "./video-player"
import { useDownload } from "@/contexts/download-context"
import { cn } from "@/lib/utils"

interface Camera {
  folder_name: string
  camera_id: number | null
  camera_name: string
  recording_count: number
}

interface Recording {
  id: string
  camera_id: number
  camera_name: string
  folder_name: string
  filename: string
  start_time: string
  duration_seconds: number
  file_size_mb: number
  file_path: string
}

interface PaginatedResponse {
  recordings: Recording[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

type SortDirection = "asc" | "desc"

export const RecordingsGallery = () => {
  // Filter states
  const [cameras, setCameras] = useState<Camera[]>([])
  const [selectedCameraId, setSelectedCameraId] = useState<string>("all")
  const [selectedDate, setSelectedDate] = useState<Date | undefined>(new Date())
  const [startTime, setStartTime] = useState("")
  const [endTime, setEndTime] = useState("")
  
  // Data states
  const [recordings, setRecordings] = useState<Recording[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedRecordings, setSelectedRecordings] = useState<Set<string>>(new Set())
  
  // Pagination states
  const [currentPage, setCurrentPage] = useState(1)
  const [totalRecordings, setTotalRecordings] = useState(0)
  const [totalPages, setTotalPages] = useState(0)
  const pageSize = 50
  
  // Download state (from context)
  const { downloadWithProgress, downloadState } = useDownload()
  const [deleting, setDeleting] = useState(false)
  
  // Sort state
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc")
  
  // Player dialog state
  const [playerOpen, setPlayerOpen] = useState(false)
  const [currentRecording, setCurrentRecording] = useState<Recording | null>(null)

  // Fetch cameras with recordings
  const fetchCameras = async () => {
    try {
      const response = await fetch("http://localhost:8001/api/recordings/cameras-with-recordings")
      if (response.ok) {
        const data = await response.json()
        setCameras(data)
      }
    } catch (error) {
      console.error("Failed to fetch cameras:", error)
    }
  }

  // Search recordings
  const searchRecordings = async (page: number = 1) => {
    setLoading(true)
    try {
      const params: Record<string, string | number | null> = {
        page,
        page_size: pageSize,
      }
      
      if (selectedCameraId !== "all") {
        params.camera_id = parseInt(selectedCameraId)
      }
      if (selectedDate) {
        params.date = format(selectedDate, "yyyy-MM-dd")
      }
      if (startTime) {
        params.start_time = startTime
      }
      if (endTime) {
        params.end_time = endTime
      }

      const response = await fetch("http://localhost:8001/api/recordings/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(params),
      })

      if (response.ok) {
        const data: PaginatedResponse = await response.json()
        setRecordings(data.recordings)
        setTotalRecordings(data.total)
        setTotalPages(data.total_pages)
        setCurrentPage(data.page)
        setSelectedRecordings(new Set()) // Clear selections on new search
      }
    } catch (error) {
      console.error("Failed to search recordings:", error)
    } finally {
      setLoading(false)
    }
  }

  // Sorted recordings
  const sortedRecordings = useMemo(() => {
    return [...recordings].sort((a, b) => {
      const dateA = new Date(a.start_time).getTime()
      const dateB = new Date(b.start_time).getTime()
      return sortDirection === "desc" ? dateB - dateA : dateA - dateB
    })
  }, [recordings, sortDirection])

  // Toggle sort direction
  const toggleSort = () => {
    setSortDirection(prev => prev === "desc" ? "asc" : "desc")
  }

  // Selection handlers
  const toggleSelectAll = () => {
    if (selectedRecordings.size === recordings.length) {
      setSelectedRecordings(new Set())
    } else {
      setSelectedRecordings(new Set(recordings.map(r => r.id)))
    }
  }

  const toggleSelectRecording = (id: string) => {
    const newSelected = new Set(selectedRecordings)
    if (newSelected.has(id)) {
      newSelected.delete(id)
    } else {
      newSelected.add(id)
    }
    setSelectedRecordings(newSelected)
  }

  // Delete single recording
  const deleteRecording = async (id: string) => {
    if (!confirm("¿Estás seguro de que quieres eliminar esta grabación?")) return
    
    setDeleting(true)
    try {
      const response = await fetch(`http://localhost:8001/api/recordings/${encodeURIComponent(id)}`, {
        method: "DELETE",
      })
      if (response.ok) {
        // Refresh current page
        await searchRecordings(currentPage)
      } else {
        const error = await response.json()
        alert(`Error al eliminar: ${error.detail}`)
      }
    } catch (error) {
      console.error("Failed to delete recording:", error)
      alert("Error al eliminar la grabación")
    } finally {
      setDeleting(false)
    }
  }

  // Bulk delete
  const bulkDelete = async () => {
    if (selectedRecordings.size === 0) return
    if (!confirm(`¿Estás seguro de que quieres eliminar ${selectedRecordings.size} grabación(es)?`)) return

    setDeleting(true)
    try {
      const response = await fetch("http://localhost:8001/api/recordings/delete-bulk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(Array.from(selectedRecordings)),
      })
      
      if (response.ok) {
        const result = await response.json()
        if (result.errors?.length > 0) {
          console.warn("Some deletions failed:", result.errors)
        }
        // Refresh current page
        await searchRecordings(currentPage)
      } else {
        const error = await response.json()
        alert(`Error al eliminar: ${error.detail}`)
      }
    } catch (error) {
      console.error("Failed to bulk delete:", error)
      alert("Error al eliminar las grabaciones")
    } finally {
      setDeleting(false)
    }
  }

  // Download recording as zip
  const downloadRecording = async (recording: Recording) => {
    const url = `http://localhost:8001/api/recordings/download/${recording.folder_name}/${recording.filename}`
    const filename = recording.filename.replace(".mp4", ".zip")
    try {
      await downloadWithProgress(url, undefined, filename, 1)
    } catch {
      alert("Error al descargar la grabación")
    }
  }

  // Bulk download as single zip
  const bulkDownload = async () => {
    if (selectedRecordings.size === 0) return
    
    const url = "http://localhost:8001/api/recordings/download-bulk"
    const options: RequestInit = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ recording_ids: Array.from(selectedRecordings) }),
    }
    const timestamp = new Date().toISOString().slice(0, 19).replace(/[:-]/g, "")
    const filename = `recordings_${timestamp}.zip`
    
    try {
      await downloadWithProgress(url, options, filename, selectedRecordings.size)
    } catch {
      alert("Error al descargar las grabaciones")
    }
  }

  // Play recording
  const playRecording = (recording: Recording) => {
    setCurrentRecording(recording)
    setPlayerOpen(true)
  }

  // Format duration
  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, "0")}`
  }

  // Format file size
  const formatSize = (mb: number): string => {
    if (mb >= 1024) {
      return `${(mb / 1024).toFixed(2)} GB`
    }
    return `${mb.toFixed(2)} MB`
  }

  // Initial load
  useEffect(() => {
    fetchCameras()
  }, [])

  // Auto-search when filters change (reset to page 1)
  useEffect(() => {
    setCurrentPage(1)
    searchRecordings(1)
  }, [selectedCameraId, selectedDate, startTime, endTime])

  // Handle manual page navigation
  const handlePageChange = (newPage: number) => {
    if (newPage !== currentPage && newPage >= 1 && newPage <= totalPages) {
      setCurrentPage(newPage)
      searchRecordings(newPage)
    }
  }

  return (
    <div className="space-y-6">
      {/* Filters Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Search className="h-5 w-5" />
            Buscar Grabaciones
          </CardTitle>
          <CardDescription>
            Filtra las grabaciones por cámara, fecha y hora
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-4">
            {/* Camera Selector */}
            <div className="space-y-2">
              <Label>Cámara</Label>
              <Select value={selectedCameraId} onValueChange={setSelectedCameraId}>
                <SelectTrigger>
                  <SelectValue placeholder="Seleccionar cámara" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todas las cámaras</SelectItem>
                  {cameras.map((camera) => (
                    <SelectItem 
                      key={camera.folder_name} 
                      value={camera.camera_id?.toString() || camera.folder_name}
                    >
                      {camera.camera_name} ({camera.recording_count})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Date Picker */}
            <div className="space-y-2">
              <Label>Fecha</Label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className={cn(
                      "w-full justify-start text-left font-normal",
                      !selectedDate && "text-muted-foreground"
                    )}
                  >
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {selectedDate ? format(selectedDate, "PPP", { locale: es }) : "Seleccionar fecha"}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0" align="start">
                  <Calendar
                    mode="single"
                    selected={selectedDate}
                    onSelect={setSelectedDate}
                    initialFocus
                  />
                </PopoverContent>
              </Popover>
            </div>

            {/* Start Time */}
            <div className="space-y-2">
              <Label>Hora inicio</Label>
              <Input
                type="time"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                placeholder="00:00"
              />
            </div>

            {/* End Time */}
            <div className="space-y-2">
              <Label>Hora fin</Label>
              <Input
                type="time"
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
                placeholder="23:59"
              />
            </div>
          </div>

          {/* Quick filters */}
          <div className="flex gap-2 mt-4">
            <Button 
              variant="outline" 
              size="sm"
              onClick={() => {
                setStartTime("")
                setEndTime("")
                setSelectedDate(new Date())
              }}
            >
              Hoy
            </Button>
            <Button 
              variant="outline" 
              size="sm"
              onClick={() => {
                const yesterday = new Date()
                yesterday.setDate(yesterday.getDate() - 1)
                setSelectedDate(yesterday)
                setStartTime("")
                setEndTime("")
              }}
            >
              Ayer
            </Button>
            <Button 
              variant="outline" 
              size="sm"
              onClick={() => {
                setSelectedDate(undefined)
                setStartTime("")
                setEndTime("")
              }}
            >
              Todas las fechas
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Results Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Grabaciones</CardTitle>
              <CardDescription>
                {loading ? "Buscando..." : `${totalRecordings} grabación(es) encontrada(s) - Página ${currentPage} de ${totalPages || 1}`}
              </CardDescription>
            </div>
            
            {/* Bulk Actions */}
            {selectedRecordings.size > 0 && (
              <div className="flex gap-2">
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={bulkDownload}
                  disabled={downloadState.isDownloading}
                >
                  {downloadState.isDownloading ? (
                    <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4 mr-1" />
                  )}
                  Descargar ({selectedRecordings.size})
                </Button>
                <Button 
                  variant="destructive" 
                  size="sm" 
                  onClick={bulkDelete}
                  disabled={deleting}
                >
                  {deleting ? (
                    <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4 mr-1" />
                  )}
                  Eliminar ({selectedRecordings.size})
                </Button>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">
                    <Checkbox 
                      checked={recordings.length > 0 && selectedRecordings.size === recordings.length}
                      onCheckedChange={toggleSelectAll}
                    />
                  </TableHead>
                  <TableHead>Cámara</TableHead>
                  <TableHead>
                    <Button variant="ghost" size="sm" className="h-8 p-0" onClick={toggleSort}>
                      Fecha/Hora
                      <ArrowUpDown className="ml-2 h-4 w-4" />
                    </Button>
                  </TableHead>
                  <TableHead>Duración</TableHead>
                  <TableHead>Tamaño</TableHead>
                  <TableHead className="text-right">Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-8">
                      <div className="flex items-center justify-center gap-2">
                        <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-primary"></div>
                        Cargando grabaciones...
                      </div>
                    </TableCell>
                  </TableRow>
                ) : sortedRecordings.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                      No se encontraron grabaciones con los filtros seleccionados
                    </TableCell>
                  </TableRow>
                ) : (
                  sortedRecordings.map((recording) => (
                    <TableRow key={recording.id}>
                      <TableCell>
                        <Checkbox 
                          checked={selectedRecordings.has(recording.id)}
                          onCheckedChange={() => toggleSelectRecording(recording.id)}
                        />
                      </TableCell>
                      <TableCell className="font-medium">{recording.camera_name}</TableCell>
                      <TableCell>
                        {format(new Date(recording.start_time), "dd/MM/yyyy HH:mm:ss")}
                      </TableCell>
                      <TableCell>{formatDuration(recording.duration_seconds)}</TableCell>
                      <TableCell>{formatSize(recording.file_size_mb)}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button 
                            variant="ghost" 
                            size="icon"
                            onClick={() => playRecording(recording)}
                            title="Reproducir"
                          >
                            <Play className="h-4 w-4" />
                          </Button>
                          <Button 
                            variant="ghost" 
                            size="icon"
                            onClick={() => downloadRecording(recording)}
                            title="Descargar"
                          >
                            <Download className="h-4 w-4" />
                          </Button>
                          <Button 
                            variant="ghost" 
                            size="icon"
                            onClick={() => deleteRecording(recording.id)}
                            title="Eliminar"
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t pt-4">
              <div className="text-sm text-muted-foreground">
                Página {currentPage} de {totalPages}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={currentPage === 1 || loading}
                >
                  <ChevronLeft className="h-4 w-4 mr-1" />
                  Anterior
                </Button>
                <div className="flex items-center gap-1">
                  {/* Page number buttons */}
                  {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                    let pageNum: number;
                    if (totalPages <= 5) {
                      pageNum = i + 1;
                    } else if (currentPage <= 3) {
                      pageNum = i + 1;
                    } else if (currentPage >= totalPages - 2) {
                      pageNum = totalPages - 4 + i;
                    } else {
                      pageNum = currentPage - 2 + i;
                    }
                    return (
                      <Button
                        key={pageNum}
                        variant={currentPage === pageNum ? "default" : "outline"}
                        size="sm"
                        className="w-8 h-8 p-0"
                        onClick={() => handlePageChange(pageNum)}
                        disabled={loading}
                      >
                        {pageNum}
                      </Button>
                    );
                  })}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={currentPage === totalPages || loading}
                >
                  Siguiente
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Video Player Dialog */}
      <Dialog open={playerOpen} onOpenChange={setPlayerOpen}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>
              {currentRecording && (
                <>
                  {currentRecording.camera_name} - {format(new Date(currentRecording.start_time), "dd/MM/yyyy HH:mm:ss")}
                </>
              )}
            </DialogTitle>
          </DialogHeader>
          <div className="aspect-video bg-black rounded-lg overflow-hidden">
            {currentRecording && (
              <VideoPlayer 
                src={currentRecording.file_path} 
                type="video/mp4"
              />
            )}
          </div>
          <div className="flex justify-between items-center text-sm text-muted-foreground">
            <span>Duración: {currentRecording && formatDuration(currentRecording.duration_seconds)}</span>
            <span>Tamaño: {currentRecording && formatSize(currentRecording.file_size_mb)}</span>
            <Button variant="outline" size="sm" onClick={() => currentRecording && downloadRecording(currentRecording)}>
              <Download className="h-4 w-4 mr-1" />
              Descargar
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
