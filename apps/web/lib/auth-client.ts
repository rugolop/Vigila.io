import { createAuthClient } from "better-auth/react";
import { genericOAuthClient } from "better-auth/client/plugins";

export const authClient = createAuthClient({
  baseURL: process.env.NEXT_PUBLIC_BETTER_AUTH_URL || "http://localhost:3000",
  plugins: [
    genericOAuthClient(),
  ],
});

// Hooks y utilidades exportadas
export const {
  signIn,
  signUp,
  signOut,
  useSession,
  getSession,
} = authClient;

// Funciones de login social
export const signInWithGoogle = async (callbackURL?: string) => {
  return authClient.signIn.social({
    provider: "google",
    callbackURL: callbackURL || "/dashboard",
  });
};

export const signInWithMicrosoft = async (callbackURL?: string) => {
  return authClient.signIn.social({
    provider: "microsoft",
    callbackURL: callbackURL || "/dashboard",
  });
};

export const signInWithAuthentik = async (callbackURL?: string) => {
  return authClient.signIn.oauth2({
    providerId: "authentik",
    callbackURL: callbackURL || "/dashboard",
  });
};

// Funciones de reset de password usando fetch directo
export const forgetPassword = async ({ email, redirectTo }: { email: string; redirectTo?: string }) => {
  try {
    const response = await fetch("/api/auth/forget-password", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email, redirectTo }),
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      return { error: { message: data.message || "Error al enviar el correo" } };
    }
    
    return { data };
  } catch (error) {
    return { error: { message: "Error de conexión" } };
  }
};

export const resetPassword = async ({ newPassword, token }: { newPassword: string; token: string }) => {
  try {
    const response = await fetch("/api/auth/reset-password", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ newPassword, token }),
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      return { error: { message: data.message || "Error al restablecer la contraseña" } };
    }
    
    return { data };
  } catch (error) {
    return { error: { message: "Error de conexión" } };
  }
};
