"use client"

import * as React from "react"
import { Video, FolderOpen, Settings, LayoutDashboard, Server, Users } from "lucide-react"
import { useTenant } from "@/hooks/use-tenant"

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  SidebarFooter,
} from "@/components/ui/sidebar"

const navigation = [
  {
    title: "General",
    items: [
      {
        title: "Dashboard",
        url: "/dashboard",
        icon: LayoutDashboard,
      },
    ],
  },
  {
    title: "Principal",
    items: [
      {
        title: "Live View",
        url: "/",
        icon: Video,
      },
      {
        title: "Recordings",
        url: "/recordings",
        icon: FolderOpen,
      },
    ],
  },
  {
    title: "Administración",
    items: [
      {
        title: "Usuarios",
        url: "/dashboard/users",
        icon: Users,
        requiredPermission: "canManageUsers" as const, // Admin o superior
      },
      {
        title: "Agentes Locales",
        url: "/agents",
        icon: Server,
      },
      {
        title: "Settings",
        url: "/settings",
        icon: Settings,
      },
    ],
  }
]

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const { hasPermission, loading } = useTenant()

  const filterItemsByPermission = (items: typeof navigation[0]["items"]) => {
    return items.filter(item => {
      // Si no requiere permiso, mostrar siempre
      if (!item.requiredPermission) return true
      
      // Si está cargando, no mostrar (evita flash de contenido)
      if (loading) return false
      
      // Verificar permiso
      return hasPermission(item.requiredPermission)
    })
  }

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader className="border-b px-6 py-4">
        <div className="flex items-center gap-2">
          <Video className="h-6 w-6 text-primary" />
          <span className="font-bold text-lg">Vigila.io</span>
        </div>
      </SidebarHeader>
      <SidebarContent>
        {navigation.map((group) => {
          const visibleItems = filterItemsByPermission(group.items)
          
          // No mostrar el grupo si no tiene items visibles
          if (visibleItems.length === 0) return null
          
          return (
            <SidebarGroup key={group.title}>
              <SidebarGroupLabel>{group.title}</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {visibleItems.map((item) => (
                    <SidebarMenuItem key={item.title}>
                      <SidebarMenuButton asChild>
                        <a href={item.url} className="flex items-center gap-3">
                          <item.icon className="h-4 w-4" />
                          <span>{item.title}</span>
                        </a>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          )
        })}
      </SidebarContent>
      <SidebarFooter className="border-t p-4">
        <p className="text-xs text-muted-foreground">v1.0.0</p>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
