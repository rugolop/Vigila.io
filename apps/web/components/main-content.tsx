"use client"

import { ReactNode } from "react"
import { useSidebar } from "@/components/ui/sidebar"

interface MainContentProps {
  children: ReactNode
}

export function MainContent({ children }: MainContentProps) {
  const { state, isMobile } = useSidebar()
  
  // En móvil no hay margin, en desktop depende del estado del sidebar
  const marginLeft = isMobile 
    ? 0 
    : state === "expanded" 
      ? "16rem"  // 256px - ancho del sidebar expandido
      : "3rem"   // 48px - ancho del sidebar con iconos
  
  return (
    <main 
      className="flex-1 flex flex-col min-h-screen w-full transition-[margin-left] duration-200 ease-linear"
      style={{ marginLeft }}
    >
      {children}
    </main>
  )
}
