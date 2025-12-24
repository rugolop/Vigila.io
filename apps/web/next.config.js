/** @type {import('next').NextConfig} */
const nextConfig = {
  // Configuración vacía de Turbopack para silenciar el warning
  // Next.js 16 usa Turbopack por defecto
  turbopack: {},
  
  // Output standalone para Docker
  output: 'standalone',
  
  // Variables de entorno públicas
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  },
};

export default nextConfig;
