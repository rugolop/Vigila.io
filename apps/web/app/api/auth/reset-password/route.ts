import { NextRequest, NextResponse } from "next/server";
import { Pool } from "pg";
import bcrypt from "bcryptjs";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL || "postgresql://user:password@localhost:5433/smartdvr",
});

export async function POST(request: NextRequest) {
  try {
    const { token, newPassword } = await request.json();

    if (!token || !newPassword) {
      return NextResponse.json(
        { message: "Token y nueva contraseña son requeridos" },
        { status: 400 }
      );
    }

    // Validar longitud de contraseña
    if (newPassword.length < 8) {
      return NextResponse.json(
        { message: "La contraseña debe tener al menos 8 caracteres" },
        { status: 400 }
      );
    }

    // Buscar token válido
    const verificationResult = await pool.query(
      `SELECT id, identifier, value, "expiresAt" 
       FROM verification 
       WHERE value = $1 
       AND identifier LIKE 'password-reset:%'
       AND "expiresAt" > NOW()`,
      [token]
    );

    if (verificationResult.rows.length === 0) {
      return NextResponse.json(
        { message: "Token inválido o expirado" },
        { status: 400 }
      );
    }

    const verification = verificationResult.rows[0];
    const userId = verification.identifier.replace("password-reset:", "");

    // Buscar usuario
    const userResult = await pool.query(
      'SELECT id, email FROM "user" WHERE id = $1',
      [userId]
    );

    if (userResult.rows.length === 0) {
      return NextResponse.json(
        { message: "Usuario no encontrado" },
        { status: 400 }
      );
    }

    // Hash de la nueva contraseña usando el mismo formato que Better Auth ($2b$)
    const salt = await bcrypt.genSalt(10);
    let hashedPassword = await bcrypt.hash(newPassword, salt);
    // Better Auth usa $2b$ prefix, bcryptjs genera $2a$ - convertir
    hashedPassword = hashedPassword.replace(/^\$2a\$/, "$2b$");

    // Actualizar contraseña en la tabla account
    const accountResult = await pool.query(
      `UPDATE account 
       SET password = $1, "updatedAt" = NOW() 
       WHERE "userId" = $2 AND "providerId" = 'credential'
       RETURNING id`,
      [hashedPassword, userId]
    );

    if (accountResult.rows.length === 0) {
      // Si no existe account con credential, crear uno
      const accountId = require("crypto").randomBytes(16).toString("hex");
      await pool.query(
        `INSERT INTO account (id, "userId", "accountId", "providerId", password, "createdAt", "updatedAt")
         VALUES ($1, $2, $2, 'credential', $3, NOW(), NOW())`,
        [accountId, userId, hashedPassword]
      );
    }

    // Eliminar token usado
    await pool.query("DELETE FROM verification WHERE id = $1", [
      verification.id,
    ]);

    console.log(`✅ Password reset successful for user: ${userResult.rows[0].email}`);

    return NextResponse.json({
      message: "Contraseña actualizada correctamente",
    });
  } catch (error) {
    console.error("Error en reset-password:", error);
    return NextResponse.json(
      { message: "Error interno del servidor" },
      { status: 500 }
    );
  }
}
