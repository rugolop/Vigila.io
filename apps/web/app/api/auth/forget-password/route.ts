import { NextRequest, NextResponse } from "next/server";
import { Pool } from "pg";
import crypto from "crypto";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL || "postgresql://user:password@localhost:5433/smartdvr",
});

export async function POST(request: NextRequest) {
  try {
    const { email, redirectTo } = await request.json();

    if (!email) {
      return NextResponse.json(
        { message: "El correo electrónico es requerido" },
        { status: 400 }
      );
    }

    // Buscar usuario por email
    const userResult = await pool.query(
      'SELECT id, email, name FROM "user" WHERE email = $1',
      [email]
    );

    if (userResult.rows.length === 0) {
      // Por seguridad, no revelar si el usuario existe o no
      return NextResponse.json({
        message: "Si el correo existe, recibirás un enlace de recuperación",
      });
    }

    const user = userResult.rows[0];

    // Generar token de reset
    const token = crypto.randomBytes(32).toString("hex");
    const expiresAt = new Date(Date.now() + 60 * 60 * 1000); // 1 hora

    // Guardar token en la tabla verification
    const verificationId = crypto.randomBytes(16).toString("hex");
    await pool.query(
      `INSERT INTO verification (id, identifier, value, "expiresAt", "createdAt", "updatedAt")
       VALUES ($1, $2, $3, $4, NOW(), NOW())
       ON CONFLICT (id) DO UPDATE SET value = $3, "expiresAt" = $4, "updatedAt" = NOW()`,
      [verificationId, `password-reset:${user.id}`, token, expiresAt]
    );

    // Construir URL de reset
    const baseUrl = process.env.BETTER_AUTH_URL || "http://localhost:3000";
    const resetUrl = `${baseUrl}${redirectTo || "/reset-password"}?token=${token}`;

    // En desarrollo, mostrar en consola
    console.log("\n" + "=".repeat(60));
    console.log("🔐 PASSWORD RESET REQUEST");
    console.log("=".repeat(60));
    console.log(`📧 User: ${user.email}`);
    console.log(`👤 Name: ${user.name || "N/A"}`);
    console.log(`🔗 Reset URL: ${resetUrl}`);
    console.log(`⏰ Expires: ${expiresAt.toISOString()}`);
    console.log("=".repeat(60) + "\n");

    // En producción, enviar email aquí
    // await sendEmail({ to: user.email, subject: "Reset password", html: `...` });

    return NextResponse.json({
      message: "Si el correo existe, recibirás un enlace de recuperación",
    });
  } catch (error) {
    console.error("Error en forget-password:", error);
    return NextResponse.json(
      { message: "Error interno del servidor" },
      { status: 500 }
    );
  }
}
