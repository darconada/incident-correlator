"""
Scorer de correlación INC ↔ TECCM.
Adaptado de jira_scorer.py para uso como servicio.
"""

from datetime import datetime
from typing import Dict, List, Any, Optional, Set
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
    "time_decay_hours": 4,
    "min_score_to_show": 0.0,
}

DEFAULT_PENALTIES = {
    "no_live_intervals": 0.8,
    "no_hosts": 0.95,
    "no_services": 0.90,
    "generic_change": 0.5,
    "long_duration_week": 0.8,
    "long_duration_month": 0.6,
    "long_duration_quarter": 0.4,
}

DEFAULT_BONUSES = {
    "proximity_exact": 1.5,     # < 30 min del INC
    "proximity_1h": 1.3,        # < 1 hora
    "proximity_2h": 1.2,        # < 2 horas
    "proximity_4h": 1.1,        # < 4 horas
}

# Umbral para considerar un cambio como "genérico"
GENERIC_CHANGE_THRESHOLD = 10

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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "reason": self.reason,
            "matches": self.matches
        }


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
    teccm_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_key": self.issue_key,
            "summary": self.summary,
            "final_score": self.final_score,
            "sub_scores": {
                "time": self.time_score.score,
                "service": self.service_score.score,
                "infra": self.infra_score.score,
                "org": self.org_score.score
            },
            "details": {
                "time_reason": self.time_score.reason,
                "time_matches": self.time_score.matches,
                "service_reason": self.service_score.reason,
                "service_matches": self.service_score.matches,
                "infra_reason": self.infra_score.reason,
                "infra_matches": self.infra_score.matches,
                "org_reason": self.org_score.reason,
                "org_matches": self.org_score.matches,
                "penalties": self.penalties_applied,
                "bonuses": self.bonuses_applied
            },
            "teccm_info": {
                "assignee": self.teccm_data.get("organization", {}).get("assignee"),
                "team": self.teccm_data.get("organization", {}).get("team"),
                "planned_start": self.teccm_data.get("times", {}).get("planned_start"),
                "planned_end": self.teccm_data.get("times", {}).get("planned_end"),
                "live_intervals": self.teccm_data.get("times", {}).get("live_intervals", []),
                "resolution": self.teccm_data.get("classification", {}).get("resolution"),
                "services": self.teccm_data.get("entities", {}).get("services", []),
                "hosts": self.teccm_data.get("entities", {}).get("hosts", []),
                "technologies": self.teccm_data.get("entities", {}).get("technologies", []),
            }
        }


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCIONES DE SCORING
# ══════════════════════════════════════════════════════════════════════════════

def parse_datetime(dt_str: str) -> Optional[datetime]:
    """Parsea un datetime ISO."""
    if not dt_str:
        return None
    try:
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

        # Calcular distancia mínima
        min_distance_minutes = float('inf')
        for interval in teccm_live_intervals:
            start = parse_datetime(interval.get('start'))
            end = parse_datetime(interval.get('end'))

            if start and end:
                if impact_time < start:
                    distance = (start - impact_time).total_seconds() / 60
                elif impact_time > end:
                    distance = (impact_time - end).total_seconds() / 60
                else:
                    distance = 0

                if distance < min_distance_minutes:
                    min_distance_minutes = distance

        if min_distance_minutes < float('inf'):
            max_minutes = decay_hours * 60
            if min_distance_minutes == 0:
                score = 100.0
            elif min_distance_minutes >= max_minutes:
                score = 0.0
            else:
                score = 100.0 * (1 - (min_distance_minutes / max_minutes) ** 0.5)

            return ScoreDetail(
                round(score, 1),
                f"Distancia a live_interval: {int(min_distance_minutes)} min",
                []
            )

    # 2. Verificar planned_start/end
    planned_start = parse_datetime(teccm_planned_start)
    planned_end = parse_datetime(teccm_planned_end)

    if planned_start and planned_end:
        if planned_start <= impact_time <= planned_end:
            return ScoreDetail(
                90.0,
                f"first_impact dentro de planned [{planned_start.strftime('%H:%M')}-{planned_end.strftime('%H:%M')}]",
                []
            )

        if impact_time < planned_start:
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
            related_groups.append({
                'group': group_name,
                'inc_services': inc_in_group,
                'teccm_services': teccm_in_group,
            })

    if related_groups:
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
    """Calcula el score de infraestructura."""
    inc_hosts_set = set(h.lower().strip() for h in inc_hosts if h)
    teccm_hosts_set = set(h.lower().strip() for h in teccm_hosts if h)
    host_matches = inc_hosts_set & teccm_hosts_set

    inc_tech_set = set(t.lower().strip() for t in inc_technologies if t)
    teccm_tech_set = set(t.lower().strip() for t in teccm_technologies if t)
    tech_matches = inc_tech_set & teccm_tech_set

    if inc_hosts_set and teccm_hosts_set:
        host_score = 100.0 if host_matches else 0.0
    else:
        host_score = 0.0

    if inc_tech_set and teccm_tech_set:
        tech_jaccard = jaccard_similarity(inc_tech_set, teccm_tech_set)
        tech_score = 50.0 + (tech_jaccard * 50.0) if tech_matches else 0.0
    else:
        tech_score = 0.0

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
    """Calcula el score organizativo."""
    score = 0.0
    matches = []
    reasons = []

    if inc_team and teccm_team:
        inc_team_lower = inc_team.lower().strip()
        teccm_team_lower = teccm_team.lower().strip()

        if inc_team_lower == teccm_team_lower:
            score += 50.0
            reasons.append("mismo equipo")
            matches.append(inc_team)
        elif inc_team_lower in teccm_team_lower or teccm_team_lower in inc_team_lower:
            score += 25.0
            reasons.append("equipo relacionado")

    inc_people_set = set(p.lower().strip() for p in inc_people if p)
    teccm_people_set = set(p.lower().strip() for p in teccm_people if p)
    people_matches = inc_people_set & teccm_people_set

    if people_matches:
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
        bonuses = DEFAULT_BONUSES.copy()

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

    final_score = (
        weights['time'] * time_score.score +
        weights['service'] * service_score.score +
        weights['infra'] * infra_score.score +
        weights['org'] * org_score.score
    )

    penalties_applied = []

    if not teccm['times'].get('live_intervals'):
        final_score *= penalties.get('no_live_intervals', 0.8)
        penalties_applied.append(f"no_live_intervals (x{penalties.get('no_live_intervals', 0.8)})")

    if not teccm['entities'].get('hosts'):
        final_score *= penalties.get('no_hosts', 0.95)
        penalties_applied.append(f"no_hosts (x{penalties.get('no_hosts', 0.95)})")

    if not teccm['entities'].get('services'):
        final_score *= penalties.get('no_services', 0.90)
        penalties_applied.append(f"no_services (x{penalties.get('no_services', 0.90)})")

    # Penalizar cambios genéricos (afectan a demasiados servicios)
    teccm_services = teccm['entities'].get('services', [])
    if len(teccm_services) > GENERIC_CHANGE_THRESHOLD:
        final_score *= penalties.get('generic_change', 0.5)
        penalties_applied.append(f"generic_change ({len(teccm_services)} services, x{penalties.get('generic_change', 0.5)})")

    # Penalizar cambios con duración muy larga (menos específicos)
    # EXCEPCIÓN: Si service + infra > 80, no penalizar (match fuerte = relevante aunque sea largo)
    planned_start = parse_datetime(teccm['times'].get('planned_start'))
    planned_end = parse_datetime(teccm['times'].get('planned_end'))

    strong_match = (service_score.score + infra_score.score) > 80

    if planned_start and planned_end and not strong_match:
        duration_hours = (planned_end - planned_start).total_seconds() / 3600

        if duration_hours > DURATION_THRESHOLDS['quarter']:
            final_score *= penalties.get('long_duration_quarter', 0.4)
            penalties_applied.append(f"long_duration ({int(duration_hours)}h > 3 months, x{penalties.get('long_duration_quarter', 0.4)})")
        elif duration_hours > DURATION_THRESHOLDS['month']:
            final_score *= penalties.get('long_duration_month', 0.6)
            penalties_applied.append(f"long_duration ({int(duration_hours)}h > 1 month, x{penalties.get('long_duration_month', 0.6)})")
        elif duration_hours > DURATION_THRESHOLDS['week']:
            final_score *= penalties.get('long_duration_week', 0.8)
            penalties_applied.append(f"long_duration ({int(duration_hours)}h > 1 week, x{penalties.get('long_duration_week', 0.8)})")

    # Aplicar bonificaciones por proximidad temporal
    bonuses_applied = []

    inc_time = parse_datetime(inc['times'].get('first_impact_time')) or \
               parse_datetime(inc['times'].get('planned_start')) or \
               parse_datetime(inc['times'].get('created_at'))

    teccm_start = parse_datetime(teccm['times'].get('planned_start'))

    if inc_time and teccm_start:
        diff_hours = abs((inc_time - teccm_start).total_seconds() / 3600)

        if diff_hours <= PROXIMITY_THRESHOLDS['exact']:
            final_score *= bonuses.get('proximity_exact', 1.5)
            bonuses_applied.append(f"proximity_exact ({diff_hours:.1f}h, x{bonuses.get('proximity_exact', 1.5)})")
        elif diff_hours <= PROXIMITY_THRESHOLDS['1h']:
            final_score *= bonuses.get('proximity_1h', 1.3)
            bonuses_applied.append(f"proximity_1h ({diff_hours:.1f}h, x{bonuses.get('proximity_1h', 1.3)})")
        elif diff_hours <= PROXIMITY_THRESHOLDS['2h']:
            final_score *= bonuses.get('proximity_2h', 1.2)
            bonuses_applied.append(f"proximity_2h ({diff_hours:.1f}h, x{bonuses.get('proximity_2h', 1.2)})")
        elif diff_hours <= PROXIMITY_THRESHOLDS['4h']:
            final_score *= bonuses.get('proximity_4h', 1.1)
            bonuses_applied.append(f"proximity_4h ({diff_hours:.1f}h, x{bonuses.get('proximity_4h', 1.1)})")

    return TECCMScore(
        issue_key=teccm['issue_key'],
        summary=teccm['summary'],
        final_score=round(final_score, 1),
        time_score=time_score,
        service_score=service_score,
        infra_score=infra_score,
        org_score=org_score,
        penalties_applied=penalties_applied,
        bonuses_applied=bonuses_applied,
        teccm_data=teccm
    )


# ══════════════════════════════════════════════════════════════════════════════
#  API DE ALTO NIVEL
# ══════════════════════════════════════════════════════════════════════════════

def calculate_ranking(
    extraction_data: Dict[str, Any],
    weights: Dict[str, float] = None,
    thresholds: Dict[str, float] = None,
    penalties: Dict[str, float] = None,
    bonuses: Dict[str, float] = None,
    min_score: float = 0.0
) -> Dict[str, Any]:
    """
    Calcula el ranking de TECCMs para un INC.

    Args:
        extraction_data: Datos de extracción (output de extract_inc_with_teccms)
        weights: Pesos para cada sub-score
        thresholds: Umbrales de configuración
        penalties: Penalizaciones
        bonuses: Bonificaciones por proximidad
        min_score: Score mínimo para incluir en ranking

    Returns:
        Dict con incident info, analysis info y ranking
    """
    weights = weights or DEFAULT_WEIGHTS.copy()
    thresholds = thresholds or DEFAULT_THRESHOLDS.copy()
    penalties = penalties or DEFAULT_PENALTIES.copy()
    bonuses = bonuses or DEFAULT_BONUSES.copy()

    # Normalizar pesos
    total_weight = sum(weights.values())
    weights = {k: v / total_weight for k, v in weights.items()}

    tickets = extraction_data.get('tickets', [])

    # Separar INC y TECCM
    incidents = [t for t in tickets if t['ticket_type'] == 'INCIDENT']
    changes = [t for t in tickets if t['ticket_type'] == 'CHANGE']

    if not incidents:
        raise ValueError("No incidents found in extraction data")

    if not changes:
        raise ValueError("No TECCMs found in extraction data")

    inc = incidents[0]

    # Calcular scores
    scores = []
    for teccm in changes:
        score = score_teccm(inc, teccm, weights, thresholds, penalties, bonuses)
        if score.final_score >= min_score:
            scores.append(score)

    # Ordenar por score
    ranking = sorted(scores, key=lambda x: x.final_score, reverse=True)

    # Construir resultado
    return {
        "incident": {
            "issue_key": inc['issue_key'],
            "summary": inc['summary'],
            "first_impact_time": inc['times'].get('first_impact_time'),
            "created_at": inc['times'].get('created_at'),
            "services": inc['entities'].get('services', []),
            "hosts": inc['entities'].get('hosts', []),
            "technologies": inc['entities'].get('technologies', []),
        },
        "analysis": {
            "teccm_analyzed": len(changes),
            "teccm_in_ranking": len(ranking),
            "scored_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "weights": weights,
            "thresholds": thresholds,
            "penalties": penalties,
            "bonuses": bonuses,
        },
        "ranking": [
            {
                "rank": i,
                **score.to_dict()
            }
            for i, score in enumerate(ranking, 1)
        ]
    }


def get_teccm_detail(
    extraction_data: Dict[str, Any],
    teccm_key: str,
    weights: Dict[str, float] = None,
    bonuses: Dict[str, float] = None
) -> Optional[Dict[str, Any]]:
    """
    Obtiene el detalle de un TECCM específico.

    Args:
        extraction_data: Datos de extracción
        teccm_key: Key del TECCM
        weights: Pesos para calcular el score
        bonuses: Bonificaciones por proximidad

    Returns:
        Dict con detalle del TECCM o None si no se encuentra
    """
    weights = weights or DEFAULT_WEIGHTS.copy()
    thresholds = DEFAULT_THRESHOLDS.copy()
    penalties = DEFAULT_PENALTIES.copy()
    bonuses = bonuses or DEFAULT_BONUSES.copy()

    # Normalizar pesos
    total_weight = sum(weights.values())
    weights = {k: v / total_weight for k, v in weights.items()}

    tickets = extraction_data.get('tickets', [])
    incidents = [t for t in tickets if t['ticket_type'] == 'INCIDENT']
    changes = [t for t in tickets if t['ticket_type'] == 'CHANGE']

    if not incidents:
        return None

    inc = incidents[0]
    teccm = next((t for t in changes if t['issue_key'].upper() == teccm_key.upper()), None)

    if not teccm:
        return None

    score = score_teccm(inc, teccm, weights, thresholds, penalties, bonuses)

    return {
        "issue_key": score.issue_key,
        "summary": score.summary,
        "final_score": score.final_score,
        "sub_scores": {
            "time": score.time_score.to_dict(),
            "service": score.service_score.to_dict(),
            "infra": score.infra_score.to_dict(),
            "org": score.org_score.to_dict(),
        },
        "penalties": score.penalties_applied,
        "bonuses": score.bonuses_applied,
        "teccm_info": score.to_dict()["teccm_info"],
    }
