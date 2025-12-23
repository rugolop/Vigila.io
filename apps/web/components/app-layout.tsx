"use client"

import { ReactNode } from "react"
import { usePathname } from "next/navigation"
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"
import { AppSidebar } from "@/components/app-sidebar"
import { DynamicBreadcrumb } from "@/components/dynamic-breadcrumb"
import { Separator } from "@/components/ui/separator"
import { MainContent } from "@/components/main-content"
import { UserNav } from "@/components/user-nav"

interface AppLayoutProps {
  children: ReactNode
}

// Rutas que no deben mostrar el sidebar (páginas de autenticación)
const AUTH_ROUTES = ["/login", "/register", "/forgot-password", "/reset-password"]

export function AppLayout({ children }: AppLayoutProps) {
  const pathname = usePathname()
  
  // No mostrar sidebar en páginas de autenticación
  const isAuthPage = AUTH_ROUTES.some(route => pathname?.startsWith(route))
  
  if (isAuthPage) {
    return <>{children}</>
  }
  
  return (
    <SidebarProvider defaultOpen={true}>
      <AppSidebar />
      <MainContent>
        <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b bg-background px-4">
          <SidebarTrigger />
          <Separator orientation="vertical" className="mr-2 h-4" />
          <DynamicBreadcrumb />
          <div className="ml-auto">
            <UserNav />
          </div>
        </header>
        <div className="flex-1 overflow-hidden">
          {children}
        </div>
      </MainContent>
    </SidebarProvider>
  )
}
