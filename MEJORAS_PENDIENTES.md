# Mejoras Pendientes - INC-TECCM Analyzer

## 1. Añadir campo "Affected Brand" de TECCMs

### Descripcion
Incluir el campo "Affected Brand" de los TECCMs en la extraccion y scoring para poder filtrar/puntuar por marca afectada.

### Estado: PENDIENTE
- **Fecha**: 2025-12-11
- **TECCM de referencia**: https://hosting-jira.1and1.org/browse/TECCM-162775

### Paso 1: Descubrir el customfield ID

**Opcion A - Via API REST:**
```
GET https://hosting-jira.1and1.org/rest/api/2/issue/TECCM-162775
```
Buscar en el JSON un campo que contenga "brand" o el valor del Affected Brand.

**Opcion B - Via script Python:**
```bash
cd backend
source venv/bin/activate
python3 << 'EOF'
from jira import JIRA

jira = JIRA(server="https://hosting-jira.1and1.org", basic_auth=("TU_USUARIO", "TU_PASSWORD"))
issue = jira.issue("TECCM-162775")

# Listar todos los campos custom
for field_name, field_value in issue.raw['fields'].items():
    if field_value and 'customfield' in field_name:
        print(f"{field_name}: {field_value}")
EOF
```

**Opcion C - Desde Jira UI:**
1. Abrir TECCM-162775 en Jira
2. Click derecho en el campo "Affected Brand" > Inspeccionar
3. Buscar el atributo `data-field-id` o similar

### Paso 2: Modificar extractor.py

**2.1 Añadir al diccionario CUSTOM_FIELDS (linea ~55):**
```python
CUSTOM_FIELDS = {
    # ... campos existentes ...

    # Brand
    "affected_brand": "customfield_XXXXX",  # <-- Reemplazar XXXXX con el ID real
}
```

**2.2 Extraer el campo en normalize_ticket() (linea ~650):**
```python
"organization": {
    "team": get_custom_field_value(fields, 'responsible_entity'),
    "brand": get_custom_field_value(fields, 'affected_brand'),  # <-- Añadir
    "assignee": safe_get(safe_get(fields, 'assignee'), 'name'),
    # ... resto ...
},
```

### Paso 3: Modificar scorer.py

**3.1 Actualizar calculate_org_score() para incluir brand:**
```python
def calculate_org_score(
    inc_people: List[str],
    inc_team: str,
    inc_brand: str,  # <-- Añadir
    teccm_people: List[str],
    teccm_team: str,
    teccm_brand: str  # <-- Añadir
) -> Tuple[int, List[str], List[str]]:
    # ... logica existente ...

    # Añadir comparacion de brand
    if inc_brand and teccm_brand:
        inc_brand_lower = inc_brand.lower().strip()
        teccm_brand_lower = teccm_brand.lower().strip()

        if inc_brand_lower == teccm_brand_lower:
            score += 50
            reasons.append("misma marca")
            matches.append(inc_brand)
        elif inc_brand_lower in teccm_brand_lower or teccm_brand_lower in inc_brand_lower:
            score += 25
            reasons.append("marca relacionada")
```

**3.2 Actualizar la llamada en calculate_ranking():**
```python
org_result = calculate_org_score(
    inc['organization'].get('people_involved', []),
    inc['organization'].get('team'),
    inc['organization'].get('brand'),  # <-- Añadir
    teccm['organization'].get('people_involved', []),
    teccm['organization'].get('team'),
    teccm['organization'].get('brand')  # <-- Añadir
)
```

### Paso 4: Modificar Frontend

**4.1 Añadir selector de Brand en DashboardPage.tsx (modal Analisis Manual):**
- Añadir estado `manualBrand`
- Añadir Select con opciones predefinidas de marcas conocidas:
  - IONOS
  - 1&1
  - Arsys
  - Strato
  - Fasthosts
  - etc.

**4.2 Incluir brand en ManualAnalysisRequest:**
```typescript
export interface ManualAnalysisRequest {
  // ... campos existentes ...
  brand?: string  // <-- Añadir
}
```

**4.3 Enviar brand en la peticion de analisis manual**

### Paso 5: Modificar Backend API

**5.1 Actualizar modelo ManualAnalysisRequest en models.py:**
```python
class ManualAnalysisRequest(BaseModel):
    # ... campos existentes ...
    brand: Optional[str] = None
```

**5.2 Usar brand en extract_manual_analysis() de extractor.py:**
```python
"organization": {
    "team": virtual_incident.get("team"),
    "brand": virtual_incident.get("brand"),  # <-- Añadir
    # ...
}
```

### Estimacion de esfuerzo
- Descubrir customfield ID: 5 min
- Modificar extractor.py: 10 min
- Modificar scorer.py: 15 min
- Modificar frontend: 20 min
- Modificar API/models: 10 min
- Testing: 15 min
- **Total: ~1-1.5 horas**

### Notas adicionales
- El campo podria ser multi-valor (array de brands) - verificar formato en JSON
- Considerar si queremos que brand sea obligatorio o opcional en analisis manual
- Podriamos extraer lista de brands unicos de TECCMs existentes para el selector

---

## 2. [Placeholder para futuras mejoras]

### Descripcion
...

### Estado: PENDIENTE
