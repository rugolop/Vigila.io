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
  const sessionCookie = request.cookies.get("better-auth.session_token");
  
  // Si no hay sesión y es una ruta protegida, redirigir al login
  if (!sessionCookie) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(loginUrl);
  }
  
  // Validar la sesión haciendo una llamada al endpoint de auth
  try {
    const sessionResponse = await fetch(
      new URL("/api/auth/get-session", request.url),
      {
        headers: {
          cookie: request.headers.get("cookie") || "",
        },
      }
    );
    
    if (!sessionResponse.ok) {
      // Sesión inválida, redirigir al login
      const loginUrl = new URL("/login", request.url);
      loginUrl.searchParams.set("callbackUrl", pathname);
      return NextResponse.redirect(loginUrl);
    }
    
    const session = await sessionResponse.json();
    
    if (!session || !session.user) {
      const loginUrl = new URL("/login", request.url);
      loginUrl.searchParams.set("callbackUrl", pathname);
      return NextResponse.redirect(loginUrl);
    }
    
    // Sesión válida, continuar
    return NextResponse.next();
  } catch {
    // En caso de error, redirigir al login
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(loginUrl);
  }
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
