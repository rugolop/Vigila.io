"use client"

import { ReactNode } from "react"
import { CameraProvider } from "@/contexts/camera-context"
import { DownloadProvider } from "@/contexts/download-context"
import { TenantProvider } from "@/hooks/use-tenant"
import { DownloadProgress } from "@/components/download-progress"

interface ProvidersProps {
  children: ReactNode
}

export function Providers({ children }: ProvidersProps) {
  return (
    <TenantProvider>
      <CameraProvider>
        <DownloadProvider>
          {children}
          <DownloadProgress />
        </DownloadProvider>
      </CameraProvider>
    </TenantProvider>
  )
}
