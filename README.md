# INC-TECCM Correlation Analyzer

Aplicacion web para analizar correlaciones entre incidentes de produccion (INC) y cambios tecnicos (TECCM) en Jira. Identifica que cambio probablemente causo un incidente mediante un sistema de scoring multi-dimensional.

## Caracteristicas

- **Extraccion paralela**: Conecta a Jira y extrae incidentes + TECCMs en ventana temporal usando multiples hilos (8 por defecto)
- **Busqueda exhaustiva de TECCMs**: 3 busquedas JQL combinadas (ventana temporal, activos al momento, sin fecha fin)
- **Scoring inteligente**: Calcula correlacion basada en tiempo, servicios, infraestructura y organizacion
- **Bonificaciones por proximidad**: TECCMs que empezaron cerca del incidente reciben bonus
- **Penalizaciones inteligentes**: Cambios muy largos o genericos son penalizados (excepto si hay strong match)
- **Ranking visual**: Muestra los TECCMs mas probables con scores detallados
- **Pesos ajustables**: Personaliza la importancia de cada dimension y recalcula en tiempo real
- **Historial**: Guarda analisis anteriores para referencia

## Arquitectura

```
+----------------------------------------------------------+
|                    Frontend (React)                       |
|              Tailwind CSS + shadcn/ui                     |
+----------------------------------------------------------+
                           | REST API
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

### Con Docker Compose (recomendado)

1. **Clonar y configurar**:
```bash
git clone https://github.com/darconada/incident-correlator.git
cd incident-correlator

# Crear fichero .env con credenciales (opcional, se pueden introducir en la UI)
cp backend/.env.example backend/.env
# Editar backend/.env con tus credenciales de Jira si quieres
```

2. **Levantar servicios**:
```bash
docker-compose up -d --build
```

3. **Acceder**:
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Docs (Swagger): http://localhost:8000/docs

### Desarrollo local

**Backend**:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend**:
```bash
cd frontend
npm install
npm run dev
```

## Configuracion

### Variables de entorno (backend/.env)

```env
# Jira (opcional - se pueden introducir en la UI)
JIRA_URL=https://URL-JIRA
JIRA_USER=tu_usuario
JIRA_PASSWORD=tu_password

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

### 2. Nuevo Analisis
- Introduce el ID del incidente (ej: `INC-117346`)
- Selecciona la ventana temporal (24h, 48h, 72h, 7d)
- Click en "Analizar"

### 3. Ver Ranking
El sistema extrae todos los TECCMs en la ventana y calcula un score de correlacion basado en:

| Dimension | Peso | Descripcion |
|-----------|------|-------------|
| **Time** | 35% | Si el impacto ocurrio durante el cambio |
| **Service** | 30% | Servicios afectados en comun |
| **Infra** | 20% | Hosts y tecnologias en comun |
| **Org** | 15% | Equipo y personas involucradas |

### 4. Ajustar Pesos
Usa los sliders en Config para modificar la importancia de cada dimension y recalcular el ranking.

### 5. Ver Detalle
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

## API Endpoints

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login con credenciales Jira |
| POST | `/api/auth/logout` | Cerrar sesion |
| GET | `/api/auth/session` | Info de sesion actual |
| POST | `/api/analysis/extract` | Iniciar extraccion |
| GET | `/api/analysis/jobs` | Listar jobs |
| GET | `/api/analysis/jobs/{id}` | Estado de un job |
| GET | `/api/analysis/{id}/ranking` | Obtener ranking |
| POST | `/api/analysis/score` | Recalcular con nuevos pesos |
| GET | `/api/analysis/{id}/teccm/{key}` | Detalle de TECCM |
| GET | `/api/config` | Obtener configuracion actual |
| PUT | `/api/config` | Actualizar configuracion |

Documentacion interactiva disponible en `/docs` (Swagger UI) y `/redoc`.

## Estructura del Proyecto

```
incident-correlator/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app
│   │   ├── config.py         # Configuracion
│   │   ├── models.py         # Pydantic models
│   │   ├── routers/          # API endpoints
│   │   │   ├── auth.py
│   │   │   ├── analysis.py
│   │   │   └── config.py
│   │   ├── services/         # Logica de negocio
│   │   │   ├── extractor.py  # Extraccion paralela de Jira
│   │   │   ├── scorer.py     # Algoritmo de scoring
│   │   │   └── jira_client.py
│   │   ├── jobs/             # Background jobs
│   │   └── db/               # Persistencia SQLite
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/       # Componentes UI
│   │   ├── pages/            # Paginas
│   │   ├── api/              # Cliente API
│   │   ├── types/            # TypeScript types
│   │   └── App.tsx
│   ├── package.json
│   └── Dockerfile
├── jira_extractor.py         # Script CLI standalone
├── jira_scorer.py            # Script CLI standalone
├── docker-compose.yml
├── docker-compose.dev.yml
└── README.md
```

## Scripts CLI Standalone

Ademas de la web, se incluyen scripts CLI que funcionan de forma independiente:

### jira_extractor.py
```bash
# Extraer un incidente con TECCMs en ventana de 48h
python jira_extractor.py --inc INC-117346 --window 48h --output extraction.json

# Extraer un ticket individual
python jira_extractor.py --ticket TECCM-123456

# Usar query JQL personalizada
python jira_extractor.py --jql "project = TECCM AND created >= -7d"
```

### jira_scorer.py
```bash
# Calcular ranking desde extraccion
python jira_scorer.py --input extraction.json

# Top 10 con detalle del primero
python jira_scorer.py --input extraction.json --top 10 --explain

# Exportar a JSON
python jira_scorer.py --input extraction.json --format json --output ranking.json

# Ajustar pesos
python jira_scorer.py --input extraction.json --weight-time 0.40 --weight-service 0.25
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

## Troubleshooting

### Error de conexion a Jira
- Verificar credenciales
- Comprobar acceso a `https://hosting-jira.1and1.org`
- VPN si es necesario

### Jobs que no terminan
- Revisar logs: `docker-compose logs -f backend`
- Verificar timeout de Jira (puede ser lento con muchos tickets)
- La extraccion paralela ayuda pero Jira puede hacer rate limiting

### Base de datos corrupta
```bash
# Borrar y recrear
rm backend/data/correlator.db
docker-compose restart backend
```

### Rate limiting de Jira
El extractor tiene retry automatico con backoff exponencial. Si persiste:
- Reducir hilos en extractor.py (`DEFAULT_THREADS`)
- Aumentar `RETRY_DELAY_BASE`

## Licencia

Uso interno.
