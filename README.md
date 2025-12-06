# INC-TECCM Correlation Analyzer

Aplicacion web para analizar correlaciones entre incidentes de produccion (INC) y cambios tecnicos (TECCM) en Jira. Identifica que cambio probablemente causo un incidente mediante un sistema de scoring multi-dimensional.

## Caracteristicas

- **Extraccion paralela**: Conecta a Jira y extrae incidentes + TECCMs en ventana temporal usando multiples hilos (8 por defecto)
- **Busqueda avanzada**: Personaliza ventanas temporales, filtros JQL, tipos de TECCM a incluir
- **Analisis manual**: Analiza TECCMs sin ticket de incidente, definiendo manualmente servicios, hosts y tecnologias afectadas
- **Scoring inteligente**: Calcula correlacion basada en tiempo, servicios, infraestructura y organizacion
- **Bonificaciones por proximidad**: TECCMs que empezaron cerca del incidente reciben bonus
- **Penalizaciones inteligentes**: Cambios muy largos o genericos son penalizados (excepto si hay strong match)
- **Ranking visual**: Muestra los TECCMs mas probables con scores detallados
- **Pesos ajustables**: Personaliza la importancia de cada dimension y recalcula en tiempo real
- **Historial enriquecido**: Muestra usuario, tipo de analisis (estandar/personalizado/manual) y resumen de opciones
- **Servicio systemd**: Arranca automaticamente con el sistema

## Arquitectura

```
+----------------------------------------------------------+
|                    Frontend (React)                       |
|              Tailwind CSS + shadcn/ui                     |
|           (servido como archivos estaticos)               |
+----------------------------------------------------------+
                           |
                           v
+----------------------------------------------------------+
|                   Backend (FastAPI)                       |
|  +-------------+  +-------------+  +-------------+       |
|  |  Extractor  |  |   Scorer    |  | Background  |       |
|  |  Service    |  |   Service   |  |    Jobs     |       |
|  | (parallel)  |  | (bonuses)   |  | (async)     |       |
|  +-------------+  +-------------+  +-------------+       |
|                           |                               |
|                      SQLite DB                            |
+----------------------------------------------------------+
                           |
                           v
                       Jira API
```

## Quick Start

### Instalacion como servicio (recomendado para produccion)

1. **Clonar y configurar**:
```bash
git clone https://github.com/darconada/incident-correlator.git
cd incident-correlator

# Configurar backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configurar frontend
cd ../frontend
npm install
npm run build
```

2. **Instalar servicio systemd**:
```bash
sudo bash install-service.sh
```

3. **Acceder**:
- Aplicacion: http://localhost:5178
- API Docs: http://localhost:5178/api-docs
- Swagger UI: http://localhost:5178/docs
- ReDoc: http://localhost:5178/redoc

4. **Comandos utiles**:
```bash
sudo systemctl status inc-teccm-analyzer   # Ver estado
sudo journalctl -u inc-teccm-analyzer -f   # Ver logs
sudo systemctl restart inc-teccm-analyzer  # Reiniciar
sudo systemctl stop inc-teccm-analyzer     # Parar
```

### Desarrollo local

**Backend**:
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

**Frontend** (en otra terminal):
```bash
cd frontend
npm run dev
```

### Con Docker Compose

```bash
docker-compose up -d --build
```
- Frontend: http://localhost:3000
- API: http://localhost:8000

## Configuracion

### Variables de entorno (backend/.env)

```env
# Jira (obligatorio)
JIRA_URL=https://URL-JIRA

# Base de datos
DATABASE_PATH=data/correlator.db

# Pesos por defecto
DEFAULT_WEIGHT_TIME=0.35
DEFAULT_WEIGHT_SERVICE=0.30
DEFAULT_WEIGHT_INFRA=0.20
DEFAULT_WEIGHT_ORG=0.15
```

## Uso

### 1. Login
Introduce tus credenciales de Jira. Se usan para conectar a la API de Jira.

### 2. Analisis con Incidente

**Analisis estandar**:
- Introduce el ID del incidente (ej: `INC-117346`)
- Selecciona la ventana temporal (24h, 48h, 72h, 7d)
- Click en "Analizar"

**Busqueda avanzada**:
- Click en "Avanzado" para personalizar:
  - Ventana antes/despues del incidente
  - Incluir TECCMs activos al momento del INC
  - Incluir TECCMs sin fecha de cierre
  - Incluir EXTERNAL MAINTENANCE en scoring
  - Filtro JQL adicional
  - Proyecto Jira a buscar
- Vista previa de las queries JQL generadas

### 3. Analisis Manual (sin ticket de incidente)

Para cuando aun no existe el ticket de incidente pero hay un problema detectado:

- Click en "Analisis Manual"
- Define:
  - **Nombre** (opcional): Para identificar el analisis
  - **Fecha/hora del impacto** (obligatorio)
  - **Servicios afectados**: Selecciona de la lista
  - **Tecnologias**: Selecciona de la lista
  - **Hosts**: Añade manualmente
  - **Equipo** (opcional)
- Configura opciones de busqueda
- Click en "Analizar"

### 4. Ver Ranking
El sistema extrae todos los TECCMs en la ventana y calcula un score de correlacion basado en:

| Dimension | Peso | Descripcion |
|-----------|------|-------------|
| **Time** | 35% | Si el impacto ocurrio durante el cambio |
| **Service** | 30% | Servicios afectados en comun |
| **Infra** | 20% | Hosts y tecnologias en comun |
| **Org** | 15% | Equipo y personas involucradas |

### 5. Historial de Analisis
El historial muestra:
- **Tipo de analisis**: Estandar, Personalizado (con icono), Manual (con icono)
- **Usuario** que lanzo el analisis
- **Resumen de opciones** si se usaron opciones no estandar

### 6. Ajustar Pesos
En la pagina de Configuracion puedes:
- Modificar pesos de cada dimension
- Configurar penalizaciones y bonificaciones
- Ver documentacion detallada del algoritmo de scoring

### 7. Ver Detalle
Click en cualquier TECCM para ver el desglose completo de sub-scores, matches, penalties y bonuses.

## Algoritmo de Scoring

### Time Score (35%)
- **100**: El `first_impact` del incidente esta dentro de un `live_interval` del TECCM
- **90**: Esta dentro del periodo planificado (planned_start - planned_end)
- **0-80**: Decay cuadratico por distancia temporal (configurable, default 4h)

### Service Score (30%)
- **Match exacto**: 50 + (Jaccard * 50) puntos
- **Match por ecosistema**: 25 puntos si ambos servicios estan en el mismo grupo (ionos-cloud, arsys, strato)
- **Sin match**: 0 puntos

### Infra Score (20%)
- **Hosts** (60%): Match exacto de hostnames = 100 puntos
- **Technologies** (40%): 50 + (Jaccard * 50) si hay match

### Org Score (15%)
- Mismo equipo: +50
- Equipo relacionado: +25
- Personas en comun: +15 por persona (max 50)

### Penalizaciones
| Penalizacion | Multiplicador | Condicion |
|--------------|---------------|-----------|
| no_live_intervals | x0.8 | TECCM sin intervalos reales documentados |
| no_hosts | x0.95 | TECCM sin hosts identificados |
| no_services | x0.90 | TECCM sin servicios identificados |
| generic_change | x0.5 | TECCM afecta >10 servicios |
| long_duration_week | x0.8 | Duracion >1 semana |
| long_duration_month | x0.6 | Duracion >1 mes |
| long_duration_quarter | x0.4 | Duracion >3 meses |

**Excepcion**: Las penalizaciones por duracion larga NO se aplican si `service_score + infra_score > 80` (strong match).

### Bonificaciones por Proximidad
| Bonus | Multiplicador | Condicion |
|-------|---------------|-----------|
| proximity_exact | x1.5 | TECCM empezo <30 min del INC |
| proximity_1h | x1.3 | TECCM empezo <1 hora del INC |
| proximity_2h | x1.2 | TECCM empezo <2 horas del INC |
| proximity_4h | x1.1 | TECCM empezo <4 horas del INC |

## API REST

### Documentacion

| URL | Descripcion |
|-----|-------------|
| `/api-docs` | Documentacion estatica integrada en la aplicacion |
| `/docs` | **Swagger UI** - Documentacion interactiva con testing en vivo |
| `/redoc` | **ReDoc** - Documentacion alternativa mas legible |
| `/openapi.json` | Especificacion OpenAPI (importable en Postman/Insomnia) |

### Endpoints

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login con credenciales Jira |
| POST | `/api/auth/logout` | Cerrar sesion |
| GET | `/api/auth/session` | Info de sesion actual |
| POST | `/api/analysis/extract` | Iniciar extraccion con INC |
| POST | `/api/analysis/manual` | Iniciar analisis manual |
| GET | `/api/analysis/options/technologies` | Lista de tecnologias disponibles |
| GET | `/api/analysis/options/services` | Lista de servicios disponibles |
| GET | `/api/analysis/jobs` | Listar jobs |
| GET | `/api/analysis/jobs/{id}` | Estado de un job |
| DELETE | `/api/analysis/jobs/{id}` | Eliminar un job |
| GET | `/api/analysis/{id}/ranking` | Obtener ranking |
| POST | `/api/analysis/score` | Recalcular con nuevos pesos |
| GET | `/api/analysis/{id}/teccm/{key}` | Detalle de TECCM |
| GET | `/api/config/weights` | Obtener pesos actuales |
| PUT | `/api/config/weights` | Actualizar pesos |
| GET | `/api/config/app` | Obtener configuracion completa |
| PUT | `/api/config/app` | Actualizar configuracion |
| GET | `/health` | Health check (no requiere auth) |

## Estructura del Proyecto

```
incident-correlator/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app + servidor estatico
│   │   ├── config.py         # Configuracion
│   │   ├── models.py         # Pydantic models
│   │   ├── routers/          # API endpoints
│   │   │   ├── auth.py
│   │   │   ├── analysis.py   # Incluye analisis manual
│   │   │   └── config.py
│   │   ├── services/         # Logica de negocio
│   │   │   ├── extractor.py  # Extraccion paralela + manual
│   │   │   ├── scorer.py     # Algoritmo de scoring
│   │   │   └── jira_client.py
│   │   ├── jobs/             # Background jobs
│   │   └── db/               # Persistencia SQLite
│   ├── data/                 # Base de datos SQLite
│   ├── venv/                 # Virtual environment
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/       # Componentes UI
│   │   ├── pages/            # Paginas (Dashboard, Analysis, Settings, ApiDocs)
│   │   ├── api/              # Cliente API
│   │   ├── types/            # TypeScript types
│   │   └── App.tsx
│   ├── dist/                 # Build de produccion
│   ├── package.json
│   └── Dockerfile
├── inc-teccm-analyzer.service  # Archivo de servicio systemd
├── install-service.sh          # Script de instalacion
├── docker-compose.yml
└── README.md
```

## Desarrollo

### Anadir nuevas tecnologias o servicios
Editar `backend/app/services/extractor.py`:
- Lista `TECHNOLOGIES` para nuevas tecnologias
- Dict `SERVICE_SYNONYMS` para sinonimos de servicios
- Dict `RELATED_SERVICE_GROUPS` para grupos de ecosistemas

### Modificar scoring
Editar `backend/app/services/scorer.py`:
- `DEFAULT_WEIGHTS` - pesos por defecto
- `DEFAULT_PENALTIES` - penalizaciones
- `DEFAULT_BONUSES` - bonificaciones por proximidad
- `DURATION_THRESHOLDS` - umbrales de duracion
- Funciones `calculate_*_score` para logica especifica

### Anadir patrones de hosts
Editar `backend/app/services/extractor.py`:
- Lista `HOST_PATTERNS` con regex
- Set `HOST_BLACKLIST` para falsos positivos
- Funcion `is_valid_host()` para validaciones

### Rebuild del frontend
Despues de cambios en el frontend:
```bash
cd frontend
npm run build
sudo systemctl restart inc-teccm-analyzer
```

## Troubleshooting

### Error de conexion a Jira
- Verificar credenciales
- Comprobar acceso a la URL de Jira configurada
- VPN si es necesario

### Jobs que no terminan
- Revisar logs: `sudo journalctl -u inc-teccm-analyzer -f`
- Verificar timeout de Jira (puede ser lento con muchos tickets)
- La extraccion paralela ayuda pero Jira puede hacer rate limiting

### Base de datos corrupta
```bash
# Borrar y recrear
rm backend/data/correlator.db
sudo systemctl restart inc-teccm-analyzer
```

### El servicio no arranca
```bash
# Ver logs detallados
sudo journalctl -u inc-teccm-analyzer -n 50

# Verificar permisos
ls -la /home/darconada@arsyslan.es/apps/inc-teccm-analyzer/backend/

# Probar manualmente
cd /home/darconada@arsyslan.es/apps/inc-teccm-analyzer/backend
./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 5178
```

### Rate limiting de Jira
El extractor tiene retry automatico con backoff exponencial. Si persiste:
- Reducir hilos en extractor.py (`DEFAULT_THREADS`)
- Aumentar `RETRY_DELAY_BASE`

## Licencia

Uso interno.
