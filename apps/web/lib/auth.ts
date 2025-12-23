import { betterAuth } from "better-auth";
import { Pool } from "pg";
import { genericOAuth } from "better-auth/plugins";

// Pool de conexión a PostgreSQL
const pool = new Pool({
  connectionString: process.env.DATABASE_URL || "postgresql://user:password@localhost:5433/smartdvr",
});

export const auth = betterAuth({
  // Base de datos PostgreSQL
  database: pool,
  
  // URL base de la aplicación
  baseURL: process.env.BETTER_AUTH_URL || "http://localhost:3000",
  
  // Secret para firmar tokens
  secret: process.env.BETTER_AUTH_SECRET || "vigila-io-secret-key-change-in-production",
  
  // Configuración de sesión
  session: {
    expiresIn: 60 * 60 * 24 * 7, // 7 días
    updateAge: 60 * 60 * 24, // Actualizar cada día
    cookieCache: {
      enabled: true,
      maxAge: 60 * 5, // 5 minutos
    },
  },
  
  // Proveedores de autenticación
  emailAndPassword: {
    enabled: true,
    requireEmailVerification: false, // Deshabilitado para desarrollo
    autoSignIn: true,
    // Configuración de reset de password
    sendResetPassword: async ({ user, url }) => {
      // En desarrollo, mostrar en consola
      console.log("=".repeat(60));
      console.log("PASSWORD RESET REQUEST");
      console.log("=".repeat(60));
      console.log(`User: ${user.email}`);
      console.log(`Reset URL: ${url}`);
      console.log("=".repeat(60));
      
      // En producción, aquí enviarías el email con un servicio como:
      // - Resend
      // - SendGrid
      // - Nodemailer
    },
  },
  
  // Proveedores OAuth sociales
  socialProviders: {
    // Google OAuth
    ...(process.env.GOOGLE_CLIENT_ID && {
      google: {
        clientId: process.env.GOOGLE_CLIENT_ID,
        clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
        scope: ["openid", "email", "profile"],
      },
    }),
    // Microsoft OAuth (Azure AD)
    ...(process.env.MICROSOFT_CLIENT_ID && {
      microsoft: {
        clientId: process.env.MICROSOFT_CLIENT_ID,
        clientSecret: process.env.MICROSOFT_CLIENT_SECRET!,
        // Usar "common" para cualquier cuenta Microsoft, o el tenant ID específico
        tenantId: process.env.MICROSOFT_TENANT_ID || "common",
        scope: ["openid", "email", "profile", "User.Read"],
      },
    }),
  },
  
  // Plugins
  plugins: [
    // Authentik como proveedor OIDC genérico
    ...(process.env.AUTHENTIK_CLIENT_ID ? [
      genericOAuth({
        config: [
          {
            providerId: "authentik",
            clientId: process.env.AUTHENTIK_CLIENT_ID,
            clientSecret: process.env.AUTHENTIK_CLIENT_SECRET!,
            discoveryUrl: `${process.env.AUTHENTIK_ISSUER}/.well-known/openid-configuration`,
            scopes: ["openid", "profile", "email"],
          },
        ],
      }),
    ] : []),
  ],
  
  // Campos adicionales de usuario
  user: {
    additionalFields: {
      role: {
        type: "string",
        required: false,
        defaultValue: "viewer",
        input: false, // No permitir que el usuario lo cambie directamente
      },
      tenantId: {
        type: "string",
        required: false,
        input: false,
      },
    },
  },
  
  // Callbacks para procesar el login
  account: {
    accountLinking: {
      enabled: true, // Permitir vincular múltiples proveedores a una cuenta
      trustedProviders: ["google", "microsoft", "authentik"],
    },
  },
});

// Tipo para el usuario autenticado
export type Session = typeof auth.$Infer.Session;
export type User = typeof auth.$Infer.Session.user;
