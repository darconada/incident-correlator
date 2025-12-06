# INC-TECCM Correlation Analyzer

Aplicación web para analizar correlaciones entre incidentes de producción (INC) y cambios (TECCM) en Jira. Identifica qué cambio probablemente causó un incidente mediante un sistema de scoring multi-dimensional.

## Características

- **Extracción automática**: Conecta a Jira y extrae incidentes + TECCMs en ventana temporal
- **Scoring inteligente**: Calcula correlación basada en tiempo, servicios, infraestructura y organización
- **Ranking visual**: Muestra los TECCMs más probables con scores detallados
- **Pesos ajustables**: Personaliza la importancia de cada dimensión y recalcula
- **Historial**: Guarda análisis anteriores para referencia

## Arquitectura

```
┌──────────────────────────────────────────────────────────┐
│                    Frontend (React)                       │
│              Tailwind CSS + shadcn/ui                     │
└──────────────────────────────────────────────────────────┘
                           │ REST API
                           ▼
┌──────────────────────────────────────────────────────────┐
│                   Backend (FastAPI)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │  Extractor  │  │   Scorer    │  │ Background  │       │
│  │  Service    │  │   Service   │  │    Jobs     │       │
│  └─────────────┘  └─────────────┘  └─────────────┘       │
│                           │                               │
│                      SQLite DB                            │
└──────────────────────────────────────────────────────────┘
                           │
                           ▼
                       Jira API
```

## Quick Start

### Con Docker Compose (recomendado)

1. **Clonar y configurar**:
```bash
cd inc-teccm-analyzer

# Crear fichero .env con credenciales (opcional, se pueden introducir en la UI)
cp backend/.env.example backend/.env
# Editar backend/.env con tus credenciales de Jira
```

2. **Levantar servicios**:
```bash
docker-compose up -d --build
```

3. **Acceder**:
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Desarrollo local

**Backend**:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend**:
```bash
cd frontend
npm install
npm run dev
```

## Configuración

### Variables de entorno (backend/.env)

```env
# Jira (opcional - se pueden introducir en la UI)
JIRA_URL=https://hosting-jira.1and1.org
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

### 2. Nuevo Análisis
- Introduce el ID del incidente (ej: `INC-117346`)
- Selecciona la ventana temporal (24h, 48h, 72h, 7d)
- Click en "Analizar"

### 3. Ver Ranking
El sistema extrae todos los TECCMs en la ventana y calcula un score de correlación basado en:

| Dimensión | Peso | Descripción |
|-----------|------|-------------|
| **Time** | 35% | Si el impacto ocurrió durante el cambio |
| **Service** | 30% | Servicios afectados en común |
| **Infra** | 20% | Hosts y tecnologías en común |
| **Org** | 15% | Equipo y personas involucradas |

### 4. Ajustar Pesos
Usa los sliders para modificar la importancia de cada dimensión y recalcular el ranking.

### 5. Ver Detalle
Click en cualquier TECCM para ver el desglose completo de sub-scores y matches.

## API Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login con credenciales Jira |
| POST | `/api/auth/logout` | Cerrar sesión |
| GET | `/api/auth/session` | Info de sesión actual |
| POST | `/api/analysis/extract` | Iniciar extracción |
| GET | `/api/analysis/jobs` | Listar jobs |
| GET | `/api/analysis/jobs/{id}` | Estado de un job |
| GET | `/api/analysis/{id}/ranking` | Obtener ranking |
| POST | `/api/analysis/score` | Recalcular con nuevos pesos |
| GET | `/api/analysis/{id}/teccm/{key}` | Detalle de TECCM |
| GET | `/api/config/weights` | Obtener pesos actuales |
| PUT | `/api/config/weights` | Actualizar pesos |

## Estructura del Proyecto

```
inc-teccm-analyzer/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app
│   │   ├── config.py         # Configuración
│   │   ├── models.py         # Pydantic models
│   │   ├── routers/          # API endpoints
│   │   ├── services/         # Lógica de negocio
│   │   ├── jobs/             # Background jobs
│   │   └── db/               # Persistencia SQLite
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/       # Componentes UI
│   │   ├── pages/            # Páginas
│   │   ├── api/              # Cliente API
│   │   ├── types/            # TypeScript types
│   │   └── App.tsx
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

## Algoritmo de Scoring

### Time Score (35%)
- **100**: El `first_impact` del incidente está dentro de un `live_interval` del TECCM
- **90**: Está dentro del período planificado
- **0-80**: Decay cuadrático por distancia temporal

### Service Score (30%)
- Similitud de Jaccard entre servicios del INC y TECCM
- Bonus de 50 puntos si hay al menos un match

### Infra Score (20%)
- **Hosts** (60%): Match exacto de hostnames
- **Technologies** (40%): Similitud de Jaccard de tecnologías

### Org Score (15%)
- Mismo equipo: +50
- Personas en común: +15 por persona (máx 50)

### Penalizaciones
- TECCM sin `live_intervals`: x0.8
- TECCM sin hosts: x0.95
- TECCM sin servicios: x0.90

## Desarrollo

### Añadir nuevos extractores
Editar `backend/app/services/extractor.py`:
- Añadir patrones en `TECHNOLOGIES` o `SERVICE_SYNONYMS`
- Modificar funciones `extract_*` para nuevos campos

### Modificar scoring
Editar `backend/app/services/scorer.py`:
- Ajustar `DEFAULT_WEIGHTS`, `DEFAULT_PENALTIES`
- Modificar funciones `calculate_*_score`

## Troubleshooting

### Error de conexión a Jira
- Verificar credenciales
- Comprobar acceso a `https://hosting-jira.1and1.org`
- VPN si es necesario

### Jobs que no terminan
- Revisar logs: `docker-compose logs -f backend`
- Verificar timeout de Jira (puede ser lento con muchos tickets)

### Base de datos corrupta
```bash
# Borrar y recrear
rm backend/data/correlator.db
docker-compose restart backend
```

## Licencia

Uso interno.
