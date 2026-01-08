import { NextResponse, type NextRequest } from "next/server";

// Rutas públicas que no requieren autenticación
const publicPaths = [
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/api/auth",
  "/_next",
  "/favicon.ico",
  "/fonts",
];

// Rutas de la API que son públicas
const publicApiPaths = [
  "/api/auth",
];

export default async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  
  // Verificar si es una ruta pública
  const isPublicPath = publicPaths.some((path) => pathname.startsWith(path));
  const isPublicApi = publicApiPaths.some((path) => pathname.startsWith(path));
  
  // Si es ruta pública, permitir acceso
  if (isPublicPath || isPublicApi) {
    return NextResponse.next();
  }
  
  // Obtener la cookie de sesión de better-auth
  // Better Auth puede usar __Secure- prefix en producción (HTTPS)
  const sessionCookie = 
    request.cookies.get("__Secure-better-auth.session_token") ||
    request.cookies.get("better-auth.session_token");
  
  // Si no hay cookie de sesión, redirigir al login
  // La validación real de la sesión se hace en los endpoints del API
  if (!sessionCookie) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(loginUrl);
  }
  
  // Cookie de sesión presente, permitir acceso
  // La validación de la sesión se hace en cada endpoint del API
  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
