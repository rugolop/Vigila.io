"use client"

import { useRouter } from "next/navigation"
import { useSession, signOut } from "@/lib/auth-client"
import { useTenant } from "@/hooks/use-tenant"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { LogOut, Settings, User, Shield, ShieldCheck, Eye, Crown } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"

const ROLE_INFO = {
  superadmin: { label: "Super Admin", icon: Crown, variant: "destructive" as const },
  admin: { label: "Admin", icon: Shield, variant: "destructive" as const },
  operator: { label: "Operador", icon: ShieldCheck, variant: "default" as const },
  viewer: { label: "Viewer", icon: Eye, variant: "secondary" as const },
}

export function UserNav() {
  const router = useRouter()
  const { data: session, isPending } = useSession()
  const { role, loading: tenantLoading } = useTenant()
  
  const handleSignOut = async () => {
    await signOut()
    router.push("/login")
    router.refresh()
  }
  
  if (isPending || tenantLoading) {
    return (
      <div className="flex items-center gap-2">
        <Skeleton className="h-8 w-8 rounded-full" />
        <Skeleton className="h-4 w-24" />
      </div>
    )
  }
  
  if (!session?.user) {
    return (
      <Button variant="outline" size="sm" onClick={() => router.push("/login")}>
        Iniciar sesión
      </Button>
    )
  }
  
  const user = session.user
  const initials = user.name
    ? user.name.split(" ").map((n) => n[0]).join("").toUpperCase().slice(0, 2)
    : user.email?.slice(0, 2).toUpperCase() || "U"
  
  const roleInfo = role ? ROLE_INFO[role] : null
  
  return (
    <div className="flex items-center gap-2">
      {roleInfo && (
        <Badge variant={roleInfo.variant} className="gap-1 hidden sm:flex">
          <roleInfo.icon className="h-3 w-3" />
          {roleInfo.label}
        </Badge>
      )}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" className="relative h-8 w-8 rounded-full">
            <Avatar className="h-8 w-8">
              <AvatarImage src={user.image || undefined} alt={user.name || "Usuario"} />
              <AvatarFallback>{initials}</AvatarFallback>
            </Avatar>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent className="w-56" align="end" forceMount>
          <DropdownMenuLabel className="font-normal">
            <div className="flex flex-col space-y-1">
              <p className="text-sm font-medium leading-none">{user.name || "Usuario"}</p>
              <p className="text-xs leading-none text-muted-foreground">
                {user.email}
              </p>
              {roleInfo && (
                <div className="flex items-center gap-1 pt-1">
                  <Badge variant={roleInfo.variant} className="gap-1 text-xs">
                    <roleInfo.icon className="h-3 w-3" />
                    {roleInfo.label}
                  </Badge>
                </div>
              )}
            </div>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => router.push("/profile")}>
            <User className="mr-2 h-4 w-4" />
            Perfil
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => router.push("/settings")}>
            <Settings className="mr-2 h-4 w-4" />
            Configuración
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={handleSignOut} className="text-red-600">
            <LogOut className="mr-2 h-4 w-4" />
            Cerrar sesión
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
