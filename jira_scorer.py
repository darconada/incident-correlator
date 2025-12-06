#!/usr/bin/env python3
"""
Scorer de correlación INC ↔ TECCM.
Toma el JSON normalizado del extractor y calcula scores de correlación.

Uso:
  python jira_scorer.py --input INC-117346_with_teccm.json
  python jira_scorer.py --input extraction.json --top 10
  python jira_scorer.py --input extraction.json --explain
  python jira_scorer.py --input extraction.json --format json --output ranking.json
  python jira_scorer.py --input extraction.json --weight-time 0.40 --weight-service 0.25
"""

import json
import argparse
import sys
import csv
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURACIÓN POR DEFECTO
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_WEIGHTS = {
    "time": 0.35,
    "service": 0.30,
    "infra": 0.20,
    "org": 0.15,
}

DEFAULT_THRESHOLDS = {
    "time_decay_hours": 4,          # Horas para decay completo del time_score
    "min_score_to_show": 0.0,       # Score mínimo para mostrar en ranking
}

DEFAULT_PENALTIES = {
    "no_live_intervals": 0.8,       # Multiplicador si TECCM no tiene live_intervals
    "no_hosts": 0.95,               # Multiplicador si TECCM no tiene hosts
    "no_services": 0.90,            # Multiplicador si TECCM no tiene services
    "generic_change": 0.5,          # Multiplicador si TECCM afecta a demasiados servicios (>10)
    "long_duration_week": 0.8,      # Multiplicador si duración > 1 semana
    "long_duration_month": 0.6,     # Multiplicador si duración > 1 mes
    "long_duration_quarter": 0.4,   # Multiplicador si duración > 3 meses
}

# Bonificaciones por proximidad temporal (TECCM empezó cerca del INC)
DEFAULT_BONUSES = {
    "proximity_exact": 1.5,         # Bonus si TECCM empezó < 30 min del INC
    "proximity_1h": 1.3,            # Bonus si TECCM empezó < 1 hora del INC
    "proximity_2h": 1.2,            # Bonus si TECCM empezó < 2 horas del INC
    "proximity_4h": 1.1,            # Bonus si TECCM empezó < 4 horas del INC
}

# Umbral para considerar un cambio como "genérico" (afecta a demasiadas áreas)
GENERIC_CHANGE_THRESHOLD = 10  # Si afecta a más de 10 servicios, probablemente es genérico

# Umbrales de duración en horas
DURATION_THRESHOLDS = {
    "week": 168,      # 7 días
    "month": 720,     # 30 días
    "quarter": 2160,  # 90 días
}

# Umbrales de proximidad en horas
PROXIMITY_THRESHOLDS = {
    "exact": 0.5,     # 30 minutos
    "1h": 1.0,
    "2h": 2.0,
    "4h": 4.0,
}

# Grupos de servicios relacionados (mismo ecosistema = match parcial)
# Si no hay match exacto pero ambos servicios están en el mismo grupo, da puntos parciales
RELATED_SERVICE_GROUPS = {
    "ionos-cloud": {
        "ic-cis", "ic-sre", "ic-oss", "ic-pss", "ic-bss", "ic-ess",
        "cloud api", "dcd", "dcd api", "compute", "network", "block storage",
        "s3 object storage", "kubernetes", "sre", "iam", "keycloak",
        "iaas provisioning", "storage provisioning", "compute provisioning",
        "network provisioning", "compute platform", "network platform",
        "storage platform", "ic-s3 object storage",
    },
    "arsys": {
        "customer area", "control panel", "mail", "dns", "webhosting",
        "dedicated server", "cloud server", "ar-cis", "ar-pss", "ar-oss",
    },
    "strato": {
        "strato-mail", "strato-webmail", "strato-server", "str-cis", "str-pss",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
#  ESTRUCTURAS DE DATOS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ScoreDetail:
    """Detalle de un sub-score."""
    score: float
    reason: str
    matches: List[str] = field(default_factory=list)


@dataclass
class TECCMScore:
    """Resultado del scoring de un TECCM."""
    issue_key: str
    summary: str
    final_score: float
    time_score: ScoreDetail
    service_score: ScoreDetail
    infra_score: ScoreDetail
    org_score: ScoreDetail
    penalties_applied: List[str] = field(default_factory=list)
    bonuses_applied: List[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCIONES DE SCORING
# ══════════════════════════════════════════════════════════════════════════════

def parse_datetime(dt_str: str) -> Optional[datetime]:
    """Parsea un datetime ISO."""
    if not dt_str:
        return None
    try:
        # Formato: 2025-07-22T12:20:00Z
        return datetime.strptime(dt_str.replace('Z', ''), "%Y-%m-%dT%H:%M:%S")
    except:
        return None


def jaccard_similarity(set1: Set[str], set2: Set[str]) -> float:
    """Calcula la similitud de Jaccard entre dos conjuntos."""
    if not set1 or not set2:
        return 0.0
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    return intersection / union if union > 0 else 0.0


def calculate_time_score(
    inc_first_impact: str,
    inc_created: str,
    teccm_live_intervals: List[Dict],
    teccm_planned_start: str,
    teccm_planned_end: str,
    decay_hours: float
) -> ScoreDetail:
    """
    Calcula el score temporal.
    
    Reglas:
    1. Si first_impact está dentro de un live_interval → 100
    2. Si está dentro de planned_start/end → 90
    3. Si está cerca (decay por distancia) → 0-80
    4. Si el cambio es posterior al incidente → 0
    """
    # Usar first_impact si existe, sino created
    impact_str = inc_first_impact or inc_created
    impact_time = parse_datetime(impact_str)
    
    if not impact_time:
        return ScoreDetail(0.0, "No se pudo determinar tiempo de impacto", [])
    
    # 1. Verificar live_intervals
    if teccm_live_intervals:
        for interval in teccm_live_intervals:
            start = parse_datetime(interval.get('start'))
            end = parse_datetime(interval.get('end'))
            
            if start and end and start <= impact_time <= end:
                return ScoreDetail(
                    100.0,
                    f"first_impact {impact_time.strftime('%H:%M')} dentro de live_interval [{start.strftime('%H:%M')}-{end.strftime('%H:%M')}]",
                    [f"{start.strftime('%Y-%m-%d %H:%M')} - {end.strftime('%H:%M')}"]
                )
        
        # Calcular distancia mínima a cualquier intervalo
        min_distance_minutes = float('inf')
        closest_interval = None
        
        for interval in teccm_live_intervals:
            start = parse_datetime(interval.get('start'))
            end = parse_datetime(interval.get('end'))
            
            if start and end:
                # Distancia al inicio o al final del intervalo
                if impact_time < start:
                    distance = (start - impact_time).total_seconds() / 60
                elif impact_time > end:
                    distance = (impact_time - end).total_seconds() / 60
                else:
                    distance = 0
                
                if distance < min_distance_minutes:
                    min_distance_minutes = distance
                    closest_interval = interval
        
        if min_distance_minutes < float('inf'):
            # Decay basado en distancia
            max_minutes = decay_hours * 60
            
            if min_distance_minutes == 0:
                score = 100.0
            elif min_distance_minutes >= max_minutes:
                score = 0.0
            else:
                # Decay cuadrático (más agresivo cerca del intervalo)
                score = 100.0 * (1 - (min_distance_minutes / max_minutes) ** 0.5)
            
            return ScoreDetail(
                round(score, 1),
                f"Distancia a live_interval: {int(min_distance_minutes)} min",
                []
            )
    
    # 2. Verificar planned_start/end (menos confiable)
    planned_start = parse_datetime(teccm_planned_start)
    planned_end = parse_datetime(teccm_planned_end)
    
    if planned_start and planned_end:
        if planned_start <= impact_time <= planned_end:
            return ScoreDetail(
                90.0,
                f"first_impact dentro de planned [{planned_start.strftime('%H:%M')}-{planned_end.strftime('%H:%M')}]",
                []
            )
        
        # Calcular distancia
        if impact_time < planned_start:
            # Impacto antes del cambio planificado → muy improbable que sea la causa
            return ScoreDetail(0.0, "Impacto anterior al cambio planificado", [])
        
        distance_minutes = (impact_time - planned_end).total_seconds() / 60
        max_minutes = decay_hours * 60
        
        if distance_minutes >= max_minutes:
            score = 0.0
        else:
            score = 80.0 * (1 - (distance_minutes / max_minutes) ** 0.5)
        
        return ScoreDetail(
            round(score, 1),
            f"Distancia a planned_end: {int(distance_minutes)} min",
            []
        )
    
    # 3. Solo tenemos planned_start
    if planned_start:
        if impact_time < planned_start:
            return ScoreDetail(0.0, "Impacto anterior al cambio", [])
        
        distance_minutes = (impact_time - planned_start).total_seconds() / 60
        max_minutes = decay_hours * 60
        
        if distance_minutes >= max_minutes:
            score = 0.0
        else:
            score = 70.0 * (1 - (distance_minutes / max_minutes) ** 0.5)
        
        return ScoreDetail(
            round(score, 1),
            f"Distancia a planned_start: {int(distance_minutes)} min",
            []
        )
    
    return ScoreDetail(0.0, "Sin información temporal del cambio", [])


def calculate_service_score(
    inc_services: List[str],
    teccm_services: List[str]
) -> ScoreDetail:
    """
    Calcula el score de servicios.
    - Match exacto: 50 + (Jaccard * 50) puntos
    - Match por grupo relacionado (mismo ecosistema): 25 puntos
    - Sin match: 0 puntos
    """
    inc_set = set(s.lower().strip() for s in inc_services if s)
    teccm_set = set(s.lower().strip() for s in teccm_services if s)
    
    if not inc_set or not teccm_set:
        return ScoreDetail(0.0, "Sin servicios para comparar", [])
    
    # 1. Buscar matches exactos
    matches = inc_set & teccm_set
    
    if matches:
        jaccard = jaccard_similarity(inc_set, teccm_set)
        # Al menos 50 puntos si hay algún match exacto, más el bonus de Jaccard
        score = 50.0 + (jaccard * 50.0)
        return ScoreDetail(
            round(score, 1),
            f"Match exacto - Jaccard: {jaccard:.2f}",
            list(matches)
        )
    
    # 2. Buscar matches por grupo relacionado
    related_groups = []
    for group_name, group_services in RELATED_SERVICE_GROUPS.items():
        inc_in_group = inc_set & group_services
        teccm_in_group = teccm_set & group_services
        
        if inc_in_group and teccm_in_group:
            # Ambos tienen servicios del mismo grupo
            related_groups.append({
                'group': group_name,
                'inc_services': inc_in_group,
                'teccm_services': teccm_in_group,
            })
    
    if related_groups:
        # Dar 25 puntos base por pertenecer al mismo ecosistema
        # Más un pequeño bonus por cantidad de servicios relacionados
        best_group = max(related_groups, key=lambda g: len(g['inc_services']) + len(g['teccm_services']))
        
        score = 25.0
        related_matches = list(best_group['inc_services']) + list(best_group['teccm_services'])
        
        return ScoreDetail(
            round(score, 1),
            f"Mismo ecosistema: {best_group['group']} ({list(best_group['inc_services'])} ↔ {list(best_group['teccm_services'])})",
            related_matches
        )
    
    # 3. Sin match
    return ScoreDetail(
        0.0,
        f"Sin match: {inc_set} vs {teccm_set}",
        []
    )


def calculate_infra_score(
    inc_hosts: List[str],
    inc_technologies: List[str],
    teccm_hosts: List[str],
    teccm_technologies: List[str]
) -> ScoreDetail:
    """Calcula el score de infraestructura (hosts + tecnologías)."""
    # Hosts
    inc_hosts_set = set(h.lower().strip() for h in inc_hosts if h)
    teccm_hosts_set = set(h.lower().strip() for h in teccm_hosts if h)
    host_matches = inc_hosts_set & teccm_hosts_set
    
    # Tecnologías
    inc_tech_set = set(t.lower().strip() for t in inc_technologies if t)
    teccm_tech_set = set(t.lower().strip() for t in teccm_technologies if t)
    tech_matches = inc_tech_set & teccm_tech_set
    
    # Score de hosts (peso 0.6)
    if inc_hosts_set and teccm_hosts_set:
        host_jaccard = jaccard_similarity(inc_hosts_set, teccm_hosts_set)
        host_score = 100.0 if host_matches else 0.0  # Match exacto de host es muy significativo
    else:
        host_score = 0.0
    
    # Score de tecnologías (peso 0.4)
    if inc_tech_set and teccm_tech_set:
        tech_jaccard = jaccard_similarity(inc_tech_set, teccm_tech_set)
        tech_score = 50.0 + (tech_jaccard * 50.0) if tech_matches else 0.0
    else:
        tech_score = 0.0
    
    # Combinar
    final_score = (host_score * 0.6) + (tech_score * 0.4)
    
    all_matches = list(host_matches) + list(tech_matches)
    
    reason_parts = []
    if host_matches:
        reason_parts.append(f"hosts: {', '.join(host_matches)}")
    if tech_matches:
        reason_parts.append(f"tech: {', '.join(tech_matches)}")
    
    reason = " | ".join(reason_parts) if reason_parts else "Sin coincidencias de infraestructura"
    
    return ScoreDetail(round(final_score, 1), reason, all_matches)


def calculate_org_score(
    inc_people: List[str],
    inc_team: str,
    teccm_people: List[str],
    teccm_team: str
) -> ScoreDetail:
    """Calcula el score organizativo (equipo + personas)."""
    score = 0.0
    matches = []
    reasons = []
    
    # Comparar equipos
    if inc_team and teccm_team:
        inc_team_lower = inc_team.lower().strip()
        teccm_team_lower = teccm_team.lower().strip()
        
        # Match exacto o parcial de equipo
        if inc_team_lower == teccm_team_lower:
            score += 50.0
            reasons.append("mismo equipo")
            matches.append(inc_team)
        elif inc_team_lower in teccm_team_lower or teccm_team_lower in inc_team_lower:
            score += 25.0
            reasons.append("equipo relacionado")
    
    # Comparar personas involucradas
    inc_people_set = set(p.lower().strip() for p in inc_people if p)
    teccm_people_set = set(p.lower().strip() for p in teccm_people if p)
    
    people_matches = inc_people_set & teccm_people_set
    
    if people_matches:
        # Más personas en común = más score
        people_score = min(50.0, len(people_matches) * 15.0)
        score += people_score
        reasons.append(f"{len(people_matches)} personas en común")
        matches.extend(list(people_matches))
    
    reason = " | ".join(reasons) if reasons else "Sin coincidencias organizativas"
    
    return ScoreDetail(min(100.0, round(score, 1)), reason, matches)


def score_teccm(
    inc: Dict[str, Any],
    teccm: Dict[str, Any],
    weights: Dict[str, float],
    thresholds: Dict[str, float],
    penalties: Dict[str, float],
    bonuses: Dict[str, float] = None
) -> TECCMScore:
    """Calcula el score completo de un TECCM respecto a un INC."""
    
    if bonuses is None:
        bonuses = DEFAULT_BONUSES
    
    # Calcular sub-scores
    time_score = calculate_time_score(
        inc['times'].get('first_impact_time'),
        inc['times'].get('created_at'),
        teccm['times'].get('live_intervals', []),
        teccm['times'].get('planned_start'),
        teccm['times'].get('planned_end'),
        thresholds['time_decay_hours']
    )
    
    service_score = calculate_service_score(
        inc['entities'].get('services', []),
        teccm['entities'].get('services', [])
    )
    
    infra_score = calculate_infra_score(
        inc['entities'].get('hosts', []),
        inc['entities'].get('technologies', []),
        teccm['entities'].get('hosts', []),
        teccm['entities'].get('technologies', [])
    )
    
    org_score = calculate_org_score(
        inc['organization'].get('people_involved', []),
        inc['organization'].get('team'),
        teccm['organization'].get('people_involved', []),
        teccm['organization'].get('team')
    )
    
    # Calcular score final ponderado
    final_score = (
        weights['time'] * time_score.score +
        weights['service'] * service_score.score +
        weights['infra'] * infra_score.score +
        weights['org'] * org_score.score
    )
    
    # Aplicar penalizaciones
    penalties_applied = []
    
    if not teccm['times'].get('live_intervals'):
        final_score *= penalties['no_live_intervals']
        penalties_applied.append(f"no_live_intervals (x{penalties['no_live_intervals']})")
    
    if not teccm['entities'].get('hosts'):
        final_score *= penalties['no_hosts']
        penalties_applied.append(f"no_hosts (x{penalties['no_hosts']})")
    
    if not teccm['entities'].get('services'):
        final_score *= penalties['no_services']
        penalties_applied.append(f"no_services (x{penalties['no_services']})")
    
    # Penalizar cambios genéricos (afectan a demasiados servicios)
    teccm_services = teccm['entities'].get('services', [])
    if len(teccm_services) > GENERIC_CHANGE_THRESHOLD:
        final_score *= penalties['generic_change']
        penalties_applied.append(f"generic_change ({len(teccm_services)} services, x{penalties['generic_change']})")
    
    # Penalizar cambios con duración muy larga (menos específicos)
    # EXCEPCIÓN: Si service + infra > 80, no penalizar (match fuerte = relevante aunque sea largo)
    planned_start = parse_datetime(teccm['times'].get('planned_start'))
    planned_end = parse_datetime(teccm['times'].get('planned_end'))
    
    strong_match = (service_score.score + infra_score.score) > 80
    
    if planned_start and planned_end and not strong_match:
        duration_hours = (planned_end - planned_start).total_seconds() / 3600
        
        if duration_hours > DURATION_THRESHOLDS['quarter']:
            final_score *= penalties['long_duration_quarter']
            penalties_applied.append(f"long_duration ({int(duration_hours)}h > 3 months, x{penalties['long_duration_quarter']})")
        elif duration_hours > DURATION_THRESHOLDS['month']:
            final_score *= penalties['long_duration_month']
            penalties_applied.append(f"long_duration ({int(duration_hours)}h > 1 month, x{penalties['long_duration_month']})")
        elif duration_hours > DURATION_THRESHOLDS['week']:
            final_score *= penalties['long_duration_week']
            penalties_applied.append(f"long_duration ({int(duration_hours)}h > 1 week, x{penalties['long_duration_week']})")
    
    # Aplicar bonificaciones por proximidad temporal
    bonuses_applied = []
    
    # Obtener tiempo del incidente (first_impact o planned_start o created_at)
    inc_time = parse_datetime(inc['times'].get('first_impact_time')) or \
               parse_datetime(inc['times'].get('planned_start')) or \
               parse_datetime(inc['times'].get('created_at'))
    
    # Obtener tiempo de inicio del TECCM
    teccm_start = parse_datetime(teccm['times'].get('planned_start'))
    
    if inc_time and teccm_start:
        # Calcular diferencia en horas (valor absoluto)
        diff_hours = abs((inc_time - teccm_start).total_seconds() / 3600)
        
        # Aplicar bonus según proximidad (solo uno, el más alto que aplique)
        if diff_hours <= PROXIMITY_THRESHOLDS['exact']:
            final_score *= bonuses['proximity_exact']
            bonuses_applied.append(f"proximity_exact ({diff_hours:.1f}h, x{bonuses['proximity_exact']})")
        elif diff_hours <= PROXIMITY_THRESHOLDS['1h']:
            final_score *= bonuses['proximity_1h']
            bonuses_applied.append(f"proximity_1h ({diff_hours:.1f}h, x{bonuses['proximity_1h']})")
        elif diff_hours <= PROXIMITY_THRESHOLDS['2h']:
            final_score *= bonuses['proximity_2h']
            bonuses_applied.append(f"proximity_2h ({diff_hours:.1f}h, x{bonuses['proximity_2h']})")
        elif diff_hours <= PROXIMITY_THRESHOLDS['4h']:
            final_score *= bonuses['proximity_4h']
            bonuses_applied.append(f"proximity_4h ({diff_hours:.1f}h, x{bonuses['proximity_4h']})")
    
    return TECCMScore(
        issue_key=teccm['issue_key'],
        summary=teccm['summary'],
        final_score=round(final_score, 1),
        time_score=time_score,
        service_score=service_score,
        infra_score=infra_score,
        org_score=org_score,
        penalties_applied=penalties_applied,
        bonuses_applied=bonuses_applied
    )


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCIONES DE OUTPUT
# ══════════════════════════════════════════════════════════════════════════════

def output_table(
    inc: Dict[str, Any],
    ranking: List[TECCMScore],
    top_n: int,
    explain: bool
):
    """Imprime el ranking en formato tabla."""
    print("=" * 100)
    print(f"  RANKING DE CORRELACIÓN: {inc['issue_key']}")
    print(f"  {inc['summary'][:80]}")
    print(f"  First impact: {inc['times'].get('first_impact_time', 'N/A')} | TECCMs analizados: {len(ranking)}")
    print("=" * 100)
    print()
    
    # Cabecera
    print(f" {'#':>3}  {'TECCM':<15} {'SCORE':>7} {'TIME':>6} {'SERV':>6} {'INFRA':>6} {'ORG':>6}  {'SUMMARY':<35}")
    print("-" * 100)
    
    # Filas
    for i, score in enumerate(ranking[:top_n], 1):
        summary_short = score.summary[:35] + "..." if len(score.summary) > 35 else score.summary
        print(
            f" {i:>3}  {score.issue_key:<15} {score.final_score:>7.1f} "
            f"{score.time_score.score:>6.1f} {score.service_score.score:>6.1f} "
            f"{score.infra_score.score:>6.1f} {score.org_score.score:>6.1f}  {summary_short:<35}"
        )
    
    print("-" * 100)
    
    # Detalle del top 1 si hay explain
    if explain and ranking:
        top1 = ranking[0]
        print()
        print("=" * 100)
        print(f"  DETALLE TOP 1: {top1.issue_key}")
        print("=" * 100)
        print(f"  time_score:    {top1.time_score.score:>6.1f}  ({top1.time_score.reason})")
        print(f"  service_score: {top1.service_score.score:>6.1f}  ({top1.service_score.reason})")
        if top1.service_score.matches:
            print(f"                         matches: {', '.join(top1.service_score.matches)}")
        print(f"  infra_score:   {top1.infra_score.score:>6.1f}  ({top1.infra_score.reason})")
        print(f"  org_score:     {top1.org_score.score:>6.1f}  ({top1.org_score.reason})")
        if top1.org_score.matches:
            print(f"                         matches: {', '.join(top1.org_score.matches[:5])}")
        if top1.penalties_applied:
            print(f"  penalties:     {', '.join(top1.penalties_applied)}")
        if top1.bonuses_applied:
            print(f"  bonuses:       {', '.join(top1.bonuses_applied)}")
        print("=" * 100)


def output_json(
    inc: Dict[str, Any],
    ranking: List[TECCMScore],
    weights: Dict[str, float],
    output_file: Optional[str]
):
    """Genera output en formato JSON."""
    result = {
        "incident": {
            "issue_key": inc['issue_key'],
            "summary": inc['summary'],
            "first_impact_time": inc['times'].get('first_impact_time'),
            "created_at": inc['times'].get('created_at')
        },
        "analysis": {
            "teccm_analyzed": len(ranking),
            "scored_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "weights": weights
        },
        "ranking": [
            {
                "rank": i,
                "issue_key": score.issue_key,
                "summary": score.summary,
                "final_score": score.final_score,
                "sub_scores": {
                    "time": score.time_score.score,
                    "service": score.service_score.score,
                    "infra": score.infra_score.score,
                    "org": score.org_score.score
                },
                "details": {
                    "time_reason": score.time_score.reason,
                    "service_matches": score.service_score.matches,
                    "infra_matches": score.infra_score.matches,
                    "org_matches": score.org_score.matches,
                    "penalties": score.penalties_applied,
                    "bonuses": score.bonuses_applied
                }
            }
            for i, score in enumerate(ranking, 1)
        ]
    }
    
    json_str = json.dumps(result, indent=2, ensure_ascii=False)
    
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(json_str)
        print(f"✓ Ranking guardado en: {output_file}")
    else:
        print(json_str)


def output_csv(
    inc: Dict[str, Any],
    ranking: List[TECCMScore],
    output_file: Optional[str]
):
    """Genera output en formato CSV."""
    rows = []
    for i, score in enumerate(ranking, 1):
        rows.append({
            'rank': i,
            'issue_key': score.issue_key,
            'final_score': score.final_score,
            'time_score': score.time_score.score,
            'service_score': score.service_score.score,
            'infra_score': score.infra_score.score,
            'org_score': score.org_score.score,
            'summary': score.summary,
            'time_reason': score.time_score.reason,
            'service_matches': ';'.join(score.service_score.matches),
            'infra_matches': ';'.join(score.infra_score.matches)
        })
    
    fieldnames = ['rank', 'issue_key', 'final_score', 'time_score', 'service_score', 
                  'infra_score', 'org_score', 'summary', 'time_reason', 
                  'service_matches', 'infra_matches']
    
    if output_file:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"✓ Ranking guardado en: {output_file}")
    else:
        import io
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        print(output.getvalue())


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Scorer de correlación INC ↔ TECCM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  %(prog)s --input INC-117346_with_teccm.json
  %(prog)s --input extraction.json --top 10 --explain
  %(prog)s --input extraction.json --format json --output ranking.json
  %(prog)s --input extraction.json --weight-time 0.40 --weight-service 0.25
        """
    )
    
    # Input/Output
    parser.add_argument("--input", "-i", required=True, help="JSON de extracción")
    parser.add_argument("--output", "-o", help="Fichero de salida")
    parser.add_argument("--format", "-f", choices=['table', 'json', 'csv'], default='table',
                        help="Formato de salida (default: table)")
    
    # Filtros
    parser.add_argument("--inc", help="Issue key del INC a analizar (si hay varios)")
    parser.add_argument("--top", type=int, default=20, help="Mostrar solo top N resultados (default: 20)")
    parser.add_argument("--min-score", type=float, default=0.0, 
                        help="Score mínimo para incluir en ranking")
    
    # Pesos
    parser.add_argument("--weight-time", type=float, default=DEFAULT_WEIGHTS['time'],
                        help=f"Peso del time_score (default: {DEFAULT_WEIGHTS['time']})")
    parser.add_argument("--weight-service", type=float, default=DEFAULT_WEIGHTS['service'],
                        help=f"Peso del service_score (default: {DEFAULT_WEIGHTS['service']})")
    parser.add_argument("--weight-infra", type=float, default=DEFAULT_WEIGHTS['infra'],
                        help=f"Peso del infra_score (default: {DEFAULT_WEIGHTS['infra']})")
    parser.add_argument("--weight-org", type=float, default=DEFAULT_WEIGHTS['org'],
                        help=f"Peso del org_score (default: {DEFAULT_WEIGHTS['org']})")
    
    # Thresholds
    parser.add_argument("--time-decay-hours", type=float, default=DEFAULT_THRESHOLDS['time_decay_hours'],
                        help=f"Horas para decay del time_score (default: {DEFAULT_THRESHOLDS['time_decay_hours']})")
    
    # Penalizaciones
    parser.add_argument("--penalty-no-intervals", type=float, default=DEFAULT_PENALTIES['no_live_intervals'],
                        help=f"Penalización si no hay live_intervals (default: {DEFAULT_PENALTIES['no_live_intervals']})")
    parser.add_argument("--penalty-no-hosts", type=float, default=DEFAULT_PENALTIES['no_hosts'],
                        help=f"Penalización si no hay hosts (default: {DEFAULT_PENALTIES['no_hosts']})")
    parser.add_argument("--penalty-no-services", type=float, default=DEFAULT_PENALTIES['no_services'],
                        help=f"Penalización si no hay services (default: {DEFAULT_PENALTIES['no_services']})")
    parser.add_argument("--penalty-generic-change", type=float, default=DEFAULT_PENALTIES['generic_change'],
                        help=f"Penalización si TECCM afecta >10 servicios (default: {DEFAULT_PENALTIES['generic_change']})")
    parser.add_argument("--penalty-long-week", type=float, default=DEFAULT_PENALTIES['long_duration_week'],
                        help=f"Penalización si duración >1 semana (default: {DEFAULT_PENALTIES['long_duration_week']})")
    parser.add_argument("--penalty-long-month", type=float, default=DEFAULT_PENALTIES['long_duration_month'],
                        help=f"Penalización si duración >1 mes (default: {DEFAULT_PENALTIES['long_duration_month']})")
    parser.add_argument("--penalty-long-quarter", type=float, default=DEFAULT_PENALTIES['long_duration_quarter'],
                        help=f"Penalización si duración >3 meses (default: {DEFAULT_PENALTIES['long_duration_quarter']})")
    
    # Opciones
    parser.add_argument("--explain", "-e", action="store_true", 
                        help="Mostrar detalle del top 1")
    
    args = parser.parse_args()
    
    # Cargar JSON de extracción
    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error leyendo {args.input}: {e}")
        sys.exit(1)
    
    tickets = data.get('tickets', [])
    
    # Separar INC y TECCM
    incidents = [t for t in tickets if t['ticket_type'] == 'INCIDENT']
    changes = [t for t in tickets if t['ticket_type'] == 'CHANGE']
    
    if not incidents:
        print("Error: No se encontraron incidentes en el JSON")
        sys.exit(1)
    
    if not changes:
        print("Error: No se encontraron TECCMs en el JSON")
        sys.exit(1)
    
    # Seleccionar INC
    if args.inc:
        inc = next((t for t in incidents if t['issue_key'] == args.inc.upper()), None)
        if not inc:
            print(f"Error: No se encontró {args.inc} en el JSON")
            sys.exit(1)
    else:
        inc = incidents[0]  # Usar el primero
    
    # Construir configuración
    weights = {
        'time': args.weight_time,
        'service': args.weight_service,
        'infra': args.weight_infra,
        'org': args.weight_org
    }
    
    # Normalizar pesos para que sumen 1
    total_weight = sum(weights.values())
    weights = {k: v / total_weight for k, v in weights.items()}
    
    thresholds = {
        'time_decay_hours': args.time_decay_hours,
        'min_score_to_show': args.min_score
    }
    
    penalties = {
        'no_live_intervals': args.penalty_no_intervals,
        'no_hosts': args.penalty_no_hosts,
        'no_services': args.penalty_no_services,
        'generic_change': args.penalty_generic_change,
        'long_duration_week': args.penalty_long_week,
        'long_duration_month': args.penalty_long_month,
        'long_duration_quarter': args.penalty_long_quarter,
    }
    
    # Calcular scores
    scores = []
    for teccm in changes:
        score = score_teccm(inc, teccm, weights, thresholds, penalties)
        if score.final_score >= args.min_score:
            scores.append(score)
    
    # Ordenar por score descendente
    ranking = sorted(scores, key=lambda x: x.final_score, reverse=True)
    
    # Output
    if args.format == 'table':
        output_table(inc, ranking, args.top, args.explain)
    elif args.format == 'json':
        output_json(inc, ranking, weights, args.output)
    elif args.format == 'csv':
        output_csv(inc, ranking, args.output)


if __name__ == "__main__":
    main()
