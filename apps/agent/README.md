# Vigila.io Local Agent

Agente local que permite conectar cámaras de tu red local al servidor Vigila.io en la nube.

## 🚀 Instalación Rápida

### Requisitos
- Python 3.9+
- FFmpeg instalado en el sistema

### Pasos

1. **Instalar FFmpeg** (si no lo tienes):
   ```bash
   # Windows (con Chocolatey)
   choco install ffmpeg
   
   # macOS
   brew install ffmpeg
   
   # Linux (Ubuntu/Debian)
   sudo apt install ffmpeg
   ```

2. **Instalar dependencias de Python**:
   ```bash
   cd apps/agent
   pip install -r requirements.txt
   ```

3. **Configurar el agente**:
   ```bash
   # Copiar archivo de configuración
   cp .env.example .env
   
   # Editar .env con tu configuración
   nano .env
   ```

4. **Obtener tu token**:
   - Inicia sesión en tu dashboard de Vigila.io
   - Ve a Configuración → Agentes Locales
   - Crea un nuevo agente y copia el token

5. **Ejecutar el agente**:
   ```bash
   python agent.py
   ```

## ⚙️ Configuración

Edita el archivo `.env`:

```env
# Token de tu cuenta Vigila.io (OBLIGATORIO)
VIGILA_TOKEN=tu_token_aqui

# URL del servidor Vigila.io
VIGILA_SERVER_URL=https://api.vigila.tudominio.com

# Nombre identificador de este agente
AGENT_NAME=mi-casa

# Intervalo de heartbeat en segundos
HEARTBEAT_INTERVAL=30

# Rango de red (opcional, auto-detecta)
# NETWORK_RANGE=192.168.1.0/24
```

## 🔧 Funcionamiento

```
┌─────────────────────────────────────────────────┐
│              TU RED LOCAL                        │
│                                                  │
│  [Cámara 1]  [Cámara 2]  [Cámara 3]             │
│      │           │           │                   │
│      └───────────┼───────────┘                   │
│                  ▼                               │
│         ┌──────────────┐                        │
│         │ Vigila Agent │                        │
│         │              │                        │
│         │ • Descubre   │                        │
│         │ • Retransmite│                        │
│         └──────┬───────┘                        │
└────────────────┼────────────────────────────────┘
                 │
                 │ Internet (RTSP sobre TCP)
                 ▼
┌─────────────────────────────────────────────────┐
│          SERVIDOR VIGILA.IO                      │
│                                                  │
│  [MediaMTX] ◄── Recibe streams                  │
│  [Backend]  ◄── Gestiona agentes                │
│  [Web]      ◄── Dashboard                       │
└─────────────────────────────────────────────────┘
```

## 📋 Comandos Disponibles

El agente recibe comandos del servidor:

| Comando | Descripción |
|---------|-------------|
| `discover` | Buscar cámaras en la red local |
| `start_relay` | Iniciar retransmisión de una cámara |
| `stop_relay` | Detener retransmisión |
| `restart_relay` | Reiniciar retransmisión |

## 🐳 Ejecutar con Docker

```bash
# Construir imagen
docker build -t vigila-agent .

# Ejecutar
docker run -d \
  --name vigila-agent \
  --network host \
  -e VIGILA_TOKEN=tu_token \
  -e VIGILA_SERVER_URL=https://api.vigila.tudominio.com \
  -e AGENT_NAME=mi-casa \
  vigila-agent
```

## 🔒 Seguridad

- El token es único por tenant y puede revocarse desde el dashboard
- Las comunicaciones usan HTTPS/TLS
- El agente NO almacena video localmente, solo retransmite
- Solo retransmite las cámaras que configures en el dashboard

## ❓ Solución de Problemas

### El agente no encuentra cámaras
- Verifica que las cámaras estén en la misma red
- Algunas cámaras requieren habilitar ONVIF en su configuración
- Prueba especificar `NETWORK_RANGE` manualmente

### FFmpeg no encontrado
- Asegúrate de que FFmpeg está instalado: `ffmpeg -version`
- En Windows, puede que necesites reiniciar la terminal

### No conecta al servidor
- Verifica la URL del servidor
- Verifica que el token sea correcto
- Revisa el firewall/antivirus

### El stream se corta
- Verifica el ancho de banda de subida
- Reduce la resolución/bitrate de la cámara
- Usa una conexión por cable en lugar de WiFi

## 📄 Licencia

MIT - Vigila.io
