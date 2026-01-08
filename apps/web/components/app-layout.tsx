"use client"

import { ReactNode, useEffect } from "react"
import { usePathname, useRouter } from "next/navigation"
import { useSession } from "@/lib/auth-client"
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
  const router = useRouter()
  const { data: session, isPending } = useSession()
  
  // No mostrar sidebar en páginas de autenticación
  const isAuthPage = AUTH_ROUTES.some(route => pathname?.startsWith(route))
  
  // Proteger rutas autenticadas
  useEffect(() => {
    // Si no está en página de auth y no hay sesión (y no está cargando), redirigir a login
    if (!isAuthPage && !isPending && !session) {
      router.push(`/login?callbackUrl=${encodeURIComponent(pathname || '/')}`)
    }
  }, [isAuthPage, session, isPending, pathname, router])
  
  // Mostrar loading mientras verifica sesión en rutas protegidas
  if (!isAuthPage && isPending) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-current border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite]" />
          <p className="mt-4 text-sm text-muted-foreground">Verificando sesión...</p>
        </div>
      </div>
    )
  }
  
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
