# Mejoras Pendientes - INC-TECCM Analyzer

## 1. Añadir campo "Affected Brand" de TECCMs

### Descripcion
Incluir el campo "Affected Brand" de los TECCMs en la extraccion y scoring para poder filtrar/puntuar por marca afectada.

### Estado: PENDIENTE
- **Fecha**: 2025-12-11
- **TECCM de referencia**: https://hosting-jira.1and1.org/browse/TECCM-162775

### Paso 1: Customfield ID (YA DESCUBIERTO)

**Campo encontrado en TECCM-162775:**
```xml
<customfield id="customfield_12938" key="com.atlassian.jira.plugin.system.customfieldtypes:multiselect">
    <customfieldname>Affected Brand</customfieldname>
    <customfieldvalues>
        <customfieldvalue key="23529">Arsys</customfieldvalue>
    </customfieldvalues>
</customfield>
```

| Campo | CustomField ID | Tipo |
|-------|---------------|------|
| **Affected Brand** | `customfield_12938` | multiselect (array) |

**Valores conocidos de Brand:**
- Arsys (key: 23529)
- (Otros por descubrir: IONOS, 1&1, Strato, Fasthosts, etc.)

### Paso 2: Modificar extractor.py

**2.1 Añadir al diccionario CUSTOM_FIELDS (linea ~55):**
```python
CUSTOM_FIELDS = {
    # ... campos existentes ...

    # Brand
    "affected_brand": "customfield_12938",  # multiselect - array de brands
}
```

**2.2 Extraer el campo en normalize_ticket() (linea ~650):**
```python
# El campo es multiselect, puede venir como array o string
affected_brands = get_custom_field_value(fields, 'affected_brand') or []
if isinstance(affected_brands, str):
    affected_brands = [affected_brands]

"organization": {
    "team": get_custom_field_value(fields, 'responsible_entity'),
    "brands": affected_brands,  # <-- Array de brands (ej: ["Arsys", "IONOS"])
    "assignee": safe_get(safe_get(fields, 'assignee'), 'name'),
    # ... resto ...
},
```

### Paso 3: Modificar scorer.py

**3.1 Actualizar calculate_org_score() para incluir brands (array):**
```python
def calculate_org_score(
    inc_people: List[str],
    inc_team: str,
    inc_brands: List[str],  # <-- Añadir (array)
    teccm_people: List[str],
    teccm_team: str,
    teccm_brands: List[str]  # <-- Añadir (array)
) -> Tuple[int, List[str], List[str]]:
    # ... logica existente ...

    # Añadir comparacion de brands
    if inc_brands and teccm_brands:
        inc_brands_lower = {b.lower().strip() for b in inc_brands}
        teccm_brands_lower = {b.lower().strip() for b in teccm_brands}

        # Interseccion de brands
        matching_brands = inc_brands_lower & teccm_brands_lower

        if matching_brands:
            score += 50
            reasons.append(f"misma marca ({len(matching_brands)} coincidencias)")
            matches.extend(matching_brands)
```

**3.2 Actualizar la llamada en calculate_ranking():**
```python
org_result = calculate_org_score(
    inc['organization'].get('people_involved', []),
    inc['organization'].get('team'),
    inc['organization'].get('brands', []),  # <-- Añadir
    teccm['organization'].get('people_involved', []),
    teccm['organization'].get('team'),
    teccm['organization'].get('brands', [])  # <-- Añadir
)
```

### Paso 4: Modificar Frontend

**4.1 Añadir selector de Brands en DashboardPage.tsx (modal Analisis Manual):**
- Añadir estado `manualBrands: string[]`
- Añadir MultiSelect con opciones predefinidas de marcas conocidas:
  - IONOS
  - 1&1
  - Arsys
  - Strato
  - Fasthosts
  - United Internet
  - (otros por confirmar)

**4.2 Incluir brands en ManualAnalysisRequest (types/index.ts):**
```typescript
export interface ManualAnalysisRequest {
  // ... campos existentes ...
  brands?: string[]  // <-- Array de brands
}
```

**4.3 Enviar brands en la peticion de analisis manual**

### Paso 5: Modificar Backend API

**5.1 Actualizar modelo ManualAnalysisRequest en models.py:**
```python
class ManualAnalysisRequest(BaseModel):
    # ... campos existentes ...
    brands: Optional[List[str]] = None  # Array de brands
```

**5.2 Usar brands en extract_manual_analysis() de extractor.py:**
```python
"organization": {
    "team": virtual_incident.get("team"),
    "brands": virtual_incident.get("brands", []),  # <-- Array
    # ...
}
```

### Estimacion de esfuerzo
- ~~Descubrir customfield ID: 5 min~~ ✅ HECHO (`customfield_12938`)
- Modificar extractor.py: 10 min
- Modificar scorer.py: 15 min
- Modificar frontend: 20 min
- Modificar API/models: 10 min
- Testing: 15 min
- **Total: ~1 hora**

### Notas adicionales
- El campo ES multi-valor (array de brands) - confirmado en XML
- Brands es opcional en analisis manual
- Podriamos crear endpoint `/api/analysis/options/brands` para listar brands disponibles
- El scoring suma +50 puntos si hay coincidencia de brand

---

## 2. [Placeholder para futuras mejoras]

### Descripcion
...

### Estado: PENDIENTE
