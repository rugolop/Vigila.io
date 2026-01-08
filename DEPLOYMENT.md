# 🚀 Guía de Despliegue en Dokploy - Vigila.io

## Arquitectura de Ambientes

| Ambiente | Rama Git | Propósito |
|----------|----------|-----------|
| **Local** | cualquiera | Desarrollo en tu máquina |
| **Preprod** | `preprod` | Testing y validación antes de producción |
| **Producción** | `main` | Ambiente de producción |

---

## 📋 Servicios a Desplegar

Cada ambiente necesita 4 servicios:

1. **PostgreSQL** - Base de datos
2. **MediaMTX** - Servidor de streaming RTSP/HLS/WebRTC
3. **Backend** - API FastAPI
4. **Web** - Frontend Next.js

---

## 🔧 Configuración en Dokploy

### 1. Crear Proyecto

1. En Dokploy, crear un nuevo proyecto: `vigila-preprod` o `vigila-prod`
2. Agregar los servicios necesarios

### 2. Servicio PostgreSQL

**Tipo:** Database → PostgreSQL

```
Nombre: postgres
Usuario: vigila_preprod (o vigila_prod)
Password: [generar password seguro]
Database: vigila_preprod (o vigila_prod)
```

### 3. Servicio MediaMTX

**Tipo:** Docker Image

```
Image: bluenviron/mediamtx:latest-ffmpeg
```

**Puertos:**
- 8554 (RTSP)
- 1935 (RTMP)
- 8888 (HLS)
- 8889 (WebRTC)
- 9997 (API)

**Volúmenes:**
- `/app/mediamtx.yml:/mediamtx.yml`
- `recordings:/recordings`

### 4. Servicio Backend (API)

**Tipo:** Git Repository (Dockerfile)

```
Repositorio: tu-repo/Vigila.io
Rama: preprod (o main para producción)
Dockerfile Path: apps/backend/Dockerfile.prod
Context: apps/backend
```

**Variables de Entorno:**
```env
DATABASE_URL=postgresql+asyncpg://vigila_preprod:PASSWORD@postgres:5432/vigila_preprod
MEDIAMTX_API_URL=http://mediamtx:9997
ENVIRONMENT=preprod
CORS_ORIGINS=https://preprod.tudominio.com
```

**Puerto:** 8001

### 5. Servicio Web (Frontend)

**Tipo:** Git Repository (Dockerfile)

```
Repositorio: tu-repo/Vigila.io
Rama: preprod (o main para producción)
Dockerfile Path: apps/web/Dockerfile
Context: . (raíz del proyecto)
```

**Build Arguments:**
```
NEXT_PUBLIC_API_URL=https://preprod-api.tudominio.com
BETTER_AUTH_URL=https://preprod.tudominio.com
```

**Variables de Entorno:**
```env
NODE_ENV=production
BETTER_AUTH_SECRET=[generar secret seguro]
DATABASE_URL=postgresql://vigila_preprod:PASSWORD@postgres:5432/vigila_preprod
```

**Puerto:** 3000

---

## 🌐 Configuración de Dominios

### Preprod
- Frontend: `preprod.vigila.tudominio.com` → web:3000
- API: `preprod-api.vigila.tudominio.com` → backend:8001
- HLS/WebRTC: `preprod-stream.vigila.tudominio.com` → mediamtx:8888

### Producción
- Frontend: `vigila.tudominio.com` → web:3000
- API: `api.vigila.tudominio.com` → backend:8001
- HLS/WebRTC: `stream.vigila.tudominio.com` → mediamtx:8888

---

## 🔄 Flujo de Trabajo Git y Despliegue Automático

### Configuración Inicial de GitHub Actions

**1. Configurar Secrets en GitHub:**

Ve a tu repositorio → Settings → Secrets and variables → Actions → New repository secret:

```
DOCKER_USERNAME: tu-usuario-dockerhub (ej: rugolop)
DOCKER_PASSWORD: tu-token-dockerhub
DOKPLOY_HOST: IP o dominio de tu servidor (ej: raspberryserver2.local o 192.168.1.100)
DOKPLOY_USER: usuario SSH (ej: root o dokploy)
DOKPLOY_SSH_KEY: tu clave privada SSH (el contenido completo de ~/.ssh/id_rsa)
DOKPLOY_SSH_PORT: puerto SSH (opcional, por defecto 22)
```

**2. Generar SSH Key (si no tienes):**

```bash
# En tu máquina local
ssh-keygen -t rsa -b 4096 -C "github-actions"

# Copiar clave pública al servidor
ssh-copy-id usuario@servidor

# Copiar clave privada para GitHub (todo el contenido)
cat ~/.ssh/id_rsa
```

### Desarrollo Local
```bash
# Trabajar en rama feature o directamente en main
git checkout -b feature/nueva-funcionalidad
# ... hacer cambios ...
git commit -m "feat: nueva funcionalidad"
git push origin feature/nueva-funcionalidad
```

### Desplegar a Producción (Automático) 🚀

```bash
# Merge a main y push
git checkout main
git merge feature/nueva-funcionalidad
git push origin main

# GitHub Actions automáticamente:
# 1. ✅ Construye las imágenes Docker
# 2. ✅ Las sube a Docker Hub (rugolop/vigila-web:latest, rugolop/vigila-backend:latest)
# 3. ✅ Se conecta al servidor vía SSH
# 4. ✅ Actualiza los servicios del stack
```

### Despliegue Manual (si es necesario)

```bash
# Desde tu servidor o vía SSH
docker service update --image rugolop/vigila-web:latest vigila_web --force
docker service update --image rugolop/vigila-backend:latest vigila_backend --force
```

---

## 🛠️ Comandos Útiles

### Desarrollo Local
```bash
# Iniciar todos los servicios locales
docker-compose -f docker-compose.local.yml up -d

# Ver logs
docker-compose -f docker-compose.local.yml logs -f

# Detener servicios
docker-compose -f docker-compose.local.yml down
```

### Crear Rama Preprod
```bash
git checkout main
git pull origin main
git checkout -b preprod
git push -u origin preprod
```

---

## 🔍 Verificar Despliegue

### Ver estado de los servicios
```bash
docker service ls
docker service ps vigila_web
docker service ps vigila_backend
```

### Ver logs en tiempo real
```bash
docker service logs -f vigila_web
docker service logs -f vigila_backend
```

### Ver GitHub Actions
- Ve a tu repositorio → Actions
- Verás el workflow "🚀 Build and Deploy to Dokploy"
- Revisa los logs de cada paso

---

## ⚠️ Notas Importantes

1. **Secrets:** Nunca commitear passwords o secrets. Usar variables de entorno en Dokploy.

2. **Base de Datos:** Cada ambiente tiene su propia base de datos. Las migraciones se ejecutan automáticamente al iniciar el backend.

3. **Recordings:** Los archivos de grabación se almacenan en volúmenes Docker. Configurar backup si es necesario.

4. **SSL/HTTPS:** Dokploy maneja los certificados SSL automáticamente con Let's Encrypt.

5. **MediaMTX:** Si necesitas acceso RTSP desde fuera, asegúrate de exponer el puerto 8554.

---

## 📊 Recursos Recomendados

| Servicio | CPU | RAM | Disco |
|----------|-----|-----|-------|
| PostgreSQL | 0.5 | 512MB | 10GB |
| MediaMTX | 1.0 | 1GB | 50GB (recordings) |
| Backend | 0.5 | 512MB | 1GB |
| Web | 0.5 | 512MB | 1GB |

**Total mínimo por ambiente:** 2.5 CPU, 2.5GB RAM, 62GB Disco
