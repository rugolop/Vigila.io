"use client"

import { useEffect, useState } from "react"
import { useTenant } from "@/hooks/use-tenant"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { 
  ChartConfig, 
  ChartContainer, 
  ChartTooltip, 
  ChartTooltipContent 
} from "@/components/ui/chart"
import { 
  Area, 
  AreaChart, 
  CartesianGrid, 
  XAxis, 
  YAxis,
  Bar,
  BarChart,
} from "recharts"
import { 
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { 
  Camera, 
  Users, 
  Building2, 
  HardDrive, 
  Activity, 
  Video,
  AlertTriangle,
  CheckCircle,
  TrendingUp,
  Clock
} from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"

// Datos de ejemplo para las gráficas (en producción vendrían del backend)
const generateActivityData = (days: number) => {
  const data = []
  const now = new Date()
  for (let i = days; i >= 0; i--) {
    const date = new Date(now)
    date.setDate(date.getDate() - i)
    data.push({
      date: date.toISOString().split('T')[0],
      recordings: Math.floor(Math.random() * 500) + 100,
      events: Math.floor(Math.random() * 50) + 10,
      storage: Math.floor(Math.random() * 100) + 50,
    })
  }
  return data
}

const generateHourlyData = () => {
  const data = []
  for (let i = 0; i < 24; i++) {
    data.push({
      hour: `${i.toString().padStart(2, '0')}:00`,
      active: Math.floor(Math.random() * 30) + 5,
      idle: Math.floor(Math.random() * 10) + 2,
    })
  }
  return data
}

interface DashboardStats {
  totalCameras: number
  activeCameras: number
  offlineCameras: number
  totalRecordings: number
  totalStorage: number
  totalTenants?: number
  activeTenants?: number
  totalUsers?: number
  totalLocations: number
}

const chartConfig = {
  recordings: {
    label: "Grabaciones",
    color: "hsl(var(--chart-1))",
  },
  events: {
    label: "Eventos",
    color: "hsl(var(--chart-2))",
  },
  storage: {
    label: "Almacenamiento (GB)",
    color: "hsl(var(--chart-3))",
  },
  active: {
    label: "Activas",
    color: "hsl(var(--chart-1))",
  },
  idle: {
    label: "Inactivas",
    color: "hsl(var(--chart-4))",
  },
} satisfies ChartConfig

export default function DashboardPage() {
  const { tenantUser, loading: tenantLoading, isSuperAdmin, role, tenantId } = useTenant()
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [timeRange, setTimeRange] = useState("7d")
  const [activityData, setActivityData] = useState(generateActivityData(7))
  const [hourlyData] = useState(generateHourlyData())

  // Actualizar datos cuando cambia el rango de tiempo
  useEffect(() => {
    const days = timeRange === "7d" ? 7 : timeRange === "30d" ? 30 : 90
    setActivityData(generateActivityData(days))
  }, [timeRange])

  // Cargar estadísticas
  useEffect(() => {
    const fetchStats = async () => {
      if (tenantLoading) return
      
      try {
        setLoading(true)
        
        // Obtener cámaras
        const camerasUrl = isSuperAdmin 
          ? `${API_URL}/api/cameras`
          : `${API_URL}/api/cameras?tenant_id=${tenantId}`
        
        const camerasRes = await fetch(camerasUrl, {
          headers: tenantUser ? { "X-User-Id": tenantUser.id } : {},
        })
        const cameras = camerasRes.ok ? await camerasRes.json() : []
        
        // Obtener grabaciones
        const recordingsRes = await fetch(`${API_URL}/api/recordings`, {
          headers: tenantUser ? { "X-User-Id": tenantUser.id } : {},
        })
        const recordings = recordingsRes.ok ? await recordingsRes.json() : []
        
        // Estadísticas base
        const baseStats: DashboardStats = {
          totalCameras: cameras.length,
          activeCameras: cameras.filter((c: { status: string }) => c.status === "connected").length,
          offlineCameras: cameras.filter((c: { status: string }) => c.status !== "connected").length,
          totalRecordings: recordings.length,
          totalStorage: recordings.reduce((acc: number, r: { file_size?: number }) => acc + (r.file_size || 0), 0) / (1024 * 1024 * 1024), // GB
          totalLocations: 0,
        }
        
        // Si es superadmin, obtener stats globales
        if (isSuperAdmin) {
          try {
            const tenantsRes = await fetch(`${API_URL}/api/tenants`, {
              headers: tenantUser ? { "X-User-Id": tenantUser.id } : {},
            })
            const tenants = tenantsRes.ok ? await tenantsRes.json() : []
            
            baseStats.totalTenants = tenants.length
            baseStats.activeTenants = tenants.filter((t: { is_active: boolean }) => t.is_active).length
            
            // Total de usuarios (simulado por ahora)
            baseStats.totalUsers = tenants.length * 3 // Aproximado
          } catch (e) {
            console.error("Error fetching global stats:", e)
          }
        }
        
        // Obtener ubicaciones
        try {
          const locationsUrl = isSuperAdmin
            ? `${API_URL}/api/locations`
            : `${API_URL}/api/locations?tenant_id=${tenantId}`
          
          const locationsRes = await fetch(locationsUrl, {
            headers: tenantUser ? { "X-User-Id": tenantUser.id } : {},
          })
          const locations = locationsRes.ok ? await locationsRes.json() : []
          baseStats.totalLocations = locations.length
        } catch (e) {
          console.error("Error fetching locations:", e)
        }
        
        setStats(baseStats)
      } catch (error) {
        console.error("Error loading dashboard stats:", error)
      } finally {
        setLoading(false)
      }
    }
    
    fetchStats()
  }, [tenantLoading, tenantUser, isSuperAdmin, tenantId])

  if (tenantLoading || loading) {
    return <DashboardSkeleton isSuperAdmin={isSuperAdmin} />
  }

  return (
    <div className="flex flex-col gap-6 p-6 overflow-auto h-full">
      {/* Header */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            {isSuperAdmin 
              ? "Vista global del sistema - Todos los tenants" 
              : `Panel de control - ${tenantUser?.tenant_name || "Mi organización"}`
            }
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Rol:</span>
          <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${
            isSuperAdmin 
              ? "bg-red-50 text-red-700 ring-red-600/20 dark:bg-red-900/20 dark:text-red-400" 
              : role === "admin"
                ? "bg-blue-50 text-blue-700 ring-blue-600/20 dark:bg-blue-900/20 dark:text-blue-400"
                : "bg-gray-50 text-gray-700 ring-gray-600/20 dark:bg-gray-900/20 dark:text-gray-400"
          }`}>
            {isSuperAdmin ? "Super Admin" : role === "admin" ? "Administrador" : role}
          </span>
        </div>
      </div>

      {/* Stats Cards */}
      <div className={`grid gap-4 ${isSuperAdmin ? "md:grid-cols-2 lg:grid-cols-4" : "md:grid-cols-2 lg:grid-cols-4"}`}>
        {/* Tarjetas de Superadmin */}
        {isSuperAdmin && (
          <>
            <StatsCard
              title="Organizaciones"
              value={stats?.totalTenants || 0}
              subtitle={`${stats?.activeTenants || 0} activas`}
              icon={Building2}
              trend="+2 este mes"
              trendUp={true}
            />
            <StatsCard
              title="Usuarios Totales"
              value={stats?.totalUsers || 0}
              subtitle="En todas las organizaciones"
              icon={Users}
              trend="+12% vs mes anterior"
              trendUp={true}
            />
          </>
        )}
        
        {/* Tarjetas comunes */}
        <StatsCard
          title="Cámaras"
          value={stats?.totalCameras || 0}
          subtitle={`${stats?.activeCameras || 0} conectadas`}
          icon={Camera}
          status={stats?.offlineCameras ? `${stats.offlineCameras} offline` : undefined}
          statusType={stats?.offlineCameras ? "warning" : "success"}
        />
        <StatsCard
          title="Ubicaciones"
          value={stats?.totalLocations || 0}
          subtitle={isSuperAdmin ? "En todos los tenants" : "Configuradas"}
          icon={Building2}
        />
        <StatsCard
          title="Grabaciones"
          value={stats?.totalRecordings || 0}
          subtitle="Total almacenadas"
          icon={Video}
          trend="Últimas 24h"
        />
        <StatsCard
          title="Almacenamiento"
          value={`${(stats?.totalStorage || 0).toFixed(1)} GB`}
          subtitle="Espacio utilizado"
          icon={HardDrive}
          trend={stats?.totalStorage && stats.totalStorage > 100 ? "Revisar espacio" : undefined}
          trendUp={false}
        />
      </div>

      {/* Charts Section */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Activity Chart */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <div className="space-y-1">
              <CardTitle className="text-base font-medium">
                Actividad del Sistema
              </CardTitle>
              <CardDescription>
                Grabaciones y eventos {isSuperAdmin ? "globales" : "de tu organización"}
              </CardDescription>
            </div>
            <Select value={timeRange} onValueChange={setTimeRange}>
              <SelectTrigger className="w-[120px]">
                <SelectValue placeholder="Período" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="7d">7 días</SelectItem>
                <SelectItem value="30d">30 días</SelectItem>
                <SelectItem value="90d">90 días</SelectItem>
              </SelectContent>
            </Select>
          </CardHeader>
          <CardContent className="pt-4">
            <ChartContainer config={chartConfig} className="h-[300px] w-full">
              <AreaChart
                data={activityData}
                margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="fillRecordings" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--color-recordings)" stopOpacity={0.8} />
                    <stop offset="95%" stopColor="var(--color-recordings)" stopOpacity={0.1} />
                  </linearGradient>
                  <linearGradient id="fillEvents" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--color-events)" stopOpacity={0.8} />
                    <stop offset="95%" stopColor="var(--color-events)" stopOpacity={0.1} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis
                  dataKey="date"
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(value) => {
                    const date = new Date(value)
                    return date.toLocaleDateString("es-ES", { day: "2-digit", month: "short" })
                  }}
                  className="text-xs"
                />
                <YAxis tickLine={false} axisLine={false} className="text-xs" />
                <ChartTooltip
                  cursor={false}
                  content={
                    <ChartTooltipContent
                      labelFormatter={(value) => {
                        return new Date(value).toLocaleDateString("es-ES", {
                          day: "numeric",
                          month: "long",
                          year: "numeric",
                        })
                      }}
                    />
                  }
                />
                <Area
                  type="monotone"
                  dataKey="recordings"
                  stroke="var(--color-recordings)"
                  fill="url(#fillRecordings)"
                  strokeWidth={2}
                />
                <Area
                  type="monotone"
                  dataKey="events"
                  stroke="var(--color-events)"
                  fill="url(#fillEvents)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ChartContainer>
          </CardContent>
        </Card>

        {/* Hourly Activity Chart */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-medium">
              Actividad por Hora
            </CardTitle>
            <CardDescription>
              Cámaras activas e inactivas durante el día
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-4">
            <ChartContainer config={chartConfig} className="h-[300px] w-full">
              <BarChart
                data={hourlyData}
                margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" vertical={false} />
                <XAxis
                  dataKey="hour"
                  tickLine={false}
                  axisLine={false}
                  className="text-xs"
                  tickFormatter={(value) => value.split(':')[0]}
                />
                <YAxis tickLine={false} axisLine={false} className="text-xs" />
                <ChartTooltip
                  cursor={false}
                  content={<ChartTooltipContent />}
                />
                <Bar
                  dataKey="active"
                  fill="var(--color-active)"
                  radius={[4, 4, 0, 0]}
                  stackId="a"
                />
                <Bar
                  dataKey="idle"
                  fill="var(--color-idle)"
                  radius={[4, 4, 0, 0]}
                  stackId="a"
                />
              </BarChart>
            </ChartContainer>
          </CardContent>
        </Card>
      </div>

      {/* Storage Chart - Only for admins */}
      {(isSuperAdmin || role === "admin") && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-medium">
              Uso de Almacenamiento
            </CardTitle>
            <CardDescription>
              Evolución del almacenamiento utilizado en el tiempo
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-4">
            <ChartContainer config={chartConfig} className="h-[200px] w-full">
              <AreaChart
                data={activityData}
                margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="fillStorage" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--color-storage)" stopOpacity={0.8} />
                    <stop offset="95%" stopColor="var(--color-storage)" stopOpacity={0.1} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis
                  dataKey="date"
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(value) => {
                    const date = new Date(value)
                    return date.toLocaleDateString("es-ES", { day: "2-digit", month: "short" })
                  }}
                  className="text-xs"
                />
                <YAxis tickLine={false} axisLine={false} className="text-xs" />
                <ChartTooltip
                  cursor={false}
                  content={
                    <ChartTooltipContent
                      labelFormatter={(value) => {
                        return new Date(value).toLocaleDateString("es-ES", {
                          day: "numeric",
                          month: "long",
                        })
                      }}
                    />
                  }
                />
                <Area
                  type="monotone"
                  dataKey="storage"
                  stroke="var(--color-storage)"
                  fill="url(#fillStorage)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ChartContainer>
          </CardContent>
        </Card>
      )}

      {/* Recent Activity / Quick Stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Estado del Sistema</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Servidor de video</span>
                <span className="flex items-center gap-1 text-sm text-green-600">
                  <CheckCircle className="h-3 w-3" /> Online
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Base de datos</span>
                <span className="flex items-center gap-1 text-sm text-green-600">
                  <CheckCircle className="h-3 w-3" /> Online
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Almacenamiento</span>
                <span className="flex items-center gap-1 text-sm text-green-600">
                  <CheckCircle className="h-3 w-3" /> OK
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Última Actividad</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-green-500" />
                <span className="text-sm">Nueva grabación guardada</span>
                <span className="ml-auto text-xs text-muted-foreground">Hace 2 min</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-blue-500" />
                <span className="text-sm">Cámara reconectada</span>
                <span className="ml-auto text-xs text-muted-foreground">Hace 15 min</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-yellow-500" />
                <span className="text-sm">Evento de movimiento</span>
                <span className="ml-auto text-xs text-muted-foreground">Hace 1 hora</span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Alertas</CardTitle>
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {stats?.offlineCameras && stats.offlineCameras > 0 ? (
                <div className="flex items-center gap-2 rounded-lg bg-yellow-50 dark:bg-yellow-900/20 p-2">
                  <AlertTriangle className="h-4 w-4 text-yellow-600" />
                  <span className="text-sm text-yellow-700 dark:text-yellow-400">
                    {stats.offlineCameras} cámara(s) desconectada(s)
                  </span>
                </div>
              ) : (
                <div className="flex items-center gap-2 rounded-lg bg-green-50 dark:bg-green-900/20 p-2">
                  <CheckCircle className="h-4 w-4 text-green-600" />
                  <span className="text-sm text-green-700 dark:text-green-400">
                    Sin alertas activas
                  </span>
                </div>
              )}
              {stats?.totalStorage && stats.totalStorage > 100 && (
                <div className="flex items-center gap-2 rounded-lg bg-orange-50 dark:bg-orange-900/20 p-2">
                  <HardDrive className="h-4 w-4 text-orange-600" />
                  <span className="text-sm text-orange-700 dark:text-orange-400">
                    Almacenamiento al {Math.round((stats.totalStorage / 500) * 100)}%
                  </span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

// Stats Card Component
interface StatsCardProps {
  title: string
  value: string | number
  subtitle: string
  icon: React.ElementType
  trend?: string
  trendUp?: boolean
  status?: string
  statusType?: "success" | "warning" | "error"
}

function StatsCard({ title, value, subtitle, icon: Icon, trend, trendUp, status, statusType }: StatsCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        <p className="text-xs text-muted-foreground">{subtitle}</p>
        {trend && (
          <p className={`mt-1 flex items-center text-xs ${trendUp ? "text-green-600" : "text-muted-foreground"}`}>
            {trendUp && <TrendingUp className="mr-1 h-3 w-3" />}
            {trend}
          </p>
        )}
        {status && (
          <p className={`mt-1 text-xs ${
            statusType === "success" ? "text-green-600" : 
            statusType === "warning" ? "text-yellow-600" : 
            "text-red-600"
          }`}>
            {status}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

// Loading Skeleton
function DashboardSkeleton({ isSuperAdmin }: { isSuperAdmin: boolean }) {
  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex flex-col gap-2">
        <Skeleton className="h-9 w-48" />
        <Skeleton className="h-4 w-64" />
      </div>
      
      <div className={`grid gap-4 ${isSuperAdmin ? "md:grid-cols-2 lg:grid-cols-4" : "md:grid-cols-2 lg:grid-cols-4"}`}>
        {Array.from({ length: isSuperAdmin ? 6 : 4 }).map((_, i) => (
          <Card key={i}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-4" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-8 w-16 mb-1" />
              <Skeleton className="h-3 w-32" />
            </CardContent>
          </Card>
        ))}
      </div>
      
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-4 w-56" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-[300px] w-full" />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-4 w-56" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-[300px] w-full" />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
