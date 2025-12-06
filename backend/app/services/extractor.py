"""
Extractor de tickets Jira.
Adaptado de jira_extractor.py para uso como servicio.
"""

import re
import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from jira import JIRA

logger = logging.getLogger(__name__)

VERSION = "1.1"
JIRA_URL = "https://hosting-jira.1and1.org"

# Configuración de paralelización
DEFAULT_THREADS = 8
MAX_RETRIES = 3
RETRY_DELAY_BASE = 2  # segundos, se multiplica exponencialmente

# ══════════════════════════════════════════════════════════════════════════════
#  MAPEOS Y PATRONES
# ══════════════════════════════════════════════════════════════════════════════

CUSTOM_FIELDS = {
    # Fechas
    "start_datetime": "customfield_10303",
    "end_datetime": "customfield_10304",
    "resolved_at": "customfield_12904",
    "completed": "customfield_12991",
    "first_response": "customfield_10818",

    # Organización
    "incident_owner": "customfield_12909",
    "incident_manager": "customfield_12910",
    "change_owner": "customfield_12984",
    "change_manager": "customfield_13026",
    "tech_escalation": "customfield_12913",
    "permitted_users": "customfield_10800",
    "responsible_entity": "customfield_15000",

    # Clasificación
    "cause": "customfield_12915",
    "effect": "customfield_12918",
    "customer_impact": "customfield_12919",
    "change_category": "customfield_12990",
    "environments": "customfield_13028",

    # Business Units
    "affected_business_units": "customfield_12921",
    "causing_business_units": "customfield_12922",
}

TECHNOLOGIES = [
    # Búsqueda/Logs
    "opensearch", "kibana", "elasticsearch", "logstash", "fluentd",
    # Web servers
    "apache", "nginx", "php", "python", "java", "nodejs", "tomcat", "jboss", "wildfly",
    # Bases de datos
    "mysql", "postgresql", "mariadb", "mongodb", "redis", "cassandra", "ceph",
    # Containers/Orchestration
    "docker", "kubernetes", "k8s", "proxmox", "vmware", "vcenter", "esxi", "openstack",
    # CI/CD
    "jenkins", "ansible", "terraform", "gitlab", "github", "bitbucket", "git", "rundeck", "salt",
    # Security/CDN
    "imperva", "cloudflare", "akamai", "waf",
    # Messaging
    "kafka", "rabbitmq", "activemq",
    # Monitoring
    "grafana", "prometheus", "zabbix", "nagios", "datadog",
    # Load balancing/Proxy
    "haproxy", "keepalived", "lvs", "varnish",
    # Cache
    "memcached",
    # Cloud providers
    "aws", "azure", "gcp",
    # Storage
    "s3", "cloudian", "hyperstore", "netbackup", "nfs",
    # Mail
    "dovecot", "postfix", "roundcube", "exim",
    # Virtualization
    "qemu", "kvm", "libvirt", "hyper-v", "virtuozzo",
    # OS/Distros
    "debian", "ubuntu", "centos", "rhel",
    # Specific products (from IONOS/1&1)
    "waas", "dcd", "clipp", "ngcs", "dave",
    # Identity/Auth
    "keycloak", "iam", "oauth", "ldap", "saml", "openid",
]

# Sinónimos de servicios conocidos
SERVICE_SYNONYMS = {
    "customer area": ["adc", "area de clientes", "customer system", "arsys customer panel", "área de clientes"],
    "control panel": ["pdc", "panel de control", "control panels"],
    "s3 object storage": ["s3", "object storage", "ic-s3", "cloudian", "hyperstore"],
    "block storage": ["ic-block storage", "block storage"],
    "compute": ["ic-compute", "compute platform", "compute provisioning"],
    "network": ["ic-network", "network platform", "network provisioning"],
    "mail": ["email", "e-mail", "mail platform", "dovecot", "postfix"],
    "dns": ["domain", "dns platform"],
    "dedicated server": ["dedicated", "bare metal", "physical server"],
    "cloud server": ["ngcs", "vps", "v-server", "cloud nx"],
    "webhosting": ["shared hosting", "sharedhosting", "web hosting"],
    "kubernetes": ["k8s", "container registry", "ic-kubernetes", "keycloak"],
}

# Patrones de hosts múltiples
HOST_PATTERNS = [
    # Patrón IONOS: s3-node-901, s3-node-91-16
    re.compile(r'\b(s3-node-\d+(?:-\d+)?)\b', re.IGNORECASE),
    # Patrón con prefijo-número: auth-out-01, accsh-j01, bex-aprtl01
    re.compile(r'\b([a-z]{2,10}-[a-z]*-?\d{1,3})\b', re.IGNORECASE),
    # Patrón clásico: llim908, srv001, bay03
    re.compile(r'\b([a-z]{2,6}\d{2,4})\b', re.IGNORECASE),
    # Patrón awsme-2385, towan-123
    re.compile(r'\b([a-z]{3,8}-\d{3,5})\b', re.IGNORECASE),
    # Patrón largo: accshappdyconsolentoolbapproda01
    re.compile(r'\b([a-z]{6,30}[a-z]\d{2})\b', re.IGNORECASE),
]

# Patrones para filtrar falsos positivos
UUID_FRAGMENT_PATTERN = re.compile(r'^[a-f0-9]{4,8}$', re.IGNORECASE)
HEX_HASH_PATTERN = re.compile(r'^[a-f0-9]{32,}$', re.IGNORECASE)

# Palabras que no son hosts aunque matcheen el patrón
HOST_BLACKLIST = {
    'https', 'http', 'image', 'browse', 'version', 'update', 'release',
    'node12', 'node10', 'node11', 'node-33', 'node-91', 'node-601', 'node-604', 'node-901',
    'utf8', 'utf16', 'iso8859', 'win1252',
    'amd64', 'x86', 'arm64',
    'eu-south-2', 'eu-central-1', 'eu-central-2', 'us-east-1', 'us-west-2',
    'region', 'regions',
    'image-2025', 'image-2024', 'image-2023', 'screenshot-1', 'screenshot-2',
}

INTERVAL_PATTERN = re.compile(
    r'\[(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}),\s*(?:(\d{2}/\d{2}/\d{4})\s+)?(\d{2}:\d{2})\]'
)
TIMELINE_PATTERN = re.compile(
    r'^(\d{8})\s+(\d{2}:\d{2})\s*-\s*(\w+):\s*(.+)$',
    re.MULTILINE
)


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCIONES DE UTILIDAD
# ══════════════════════════════════════════════════════════════════════════════

def safe_get(obj, attr, default=None):
    """Obtiene un atributo de forma segura."""
    if obj is None:
        return default
    return getattr(obj, attr, default) if hasattr(obj, attr) else default


def parse_window(window_str: str) -> timedelta:
    """Parsea una ventana temporal como '48h', '2d', '120m'."""
    match = re.match(r'^(\d+)([hdm])$', window_str.lower())
    if not match:
        raise ValueError(f"Formato de ventana inválido: {window_str}")

    value, unit = int(match.group(1)), match.group(2)

    if unit == 'h':
        return timedelta(hours=value)
    elif unit == 'd':
        return timedelta(days=value)
    elif unit == 'm':
        return timedelta(minutes=value)


def normalize_datetime(dt_str: str) -> Optional[str]:
    """Normaliza una fecha de Jira a formato ISO."""
    if not dt_str:
        return None
    try:
        dt = datetime.strptime(dt_str[:19], "%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except:
        return dt_str


def parse_interval_date(date_str: str, time_str: str, reference_date: str = None) -> Optional[str]:
    """Parsea fecha y hora de un intervalo a ISO format."""
    try:
        if date_str:
            dt = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
        elif reference_date:
            ref = datetime.strptime(reference_date, "%d/%m/%Y")
            time = datetime.strptime(time_str, "%H:%M")
            dt = ref.replace(hour=time.hour, minute=time.minute)
        else:
            return None
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except:
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  EXTRACTORES ESPECÍFICOS
# ══════════════════════════════════════════════════════════════════════════════

def is_valid_host(hostname: str) -> bool:
    """Valida si un string es un hostname válido (no UUID, no hash, no blacklist)."""
    hostname = hostname.lower().strip()

    # Filtrar blacklist
    if hostname in HOST_BLACKLIST:
        return False

    # Filtrar fragmentos de UUID (4-8 caracteres hex puros)
    if UUID_FRAGMENT_PATTERN.match(hostname):
        return False

    # Filtrar hashes largos
    if HEX_HASH_PATTERN.match(hostname):
        return False

    # Filtrar si es solo números
    if hostname.replace('-', '').isdigit():
        return False

    # Filtrar patrones de versiones: v1, v2, 8.1.3, etc
    if re.match(r'^v?\d+(\.\d+)*$', hostname):
        return False

    # Debe tener al menos una letra
    if not any(c.isalpha() for c in hostname):
        return False

    # Filtrar fragmentos incompletos de s3-node-*
    if re.match(r'^node-\d+$', hostname):
        return False

    # Filtrar regiones cloud (eu-south-2, us-east-1, etc.)
    if re.match(r'^(eu|us|ap|sa|af|me)-(north|south|east|west|central)-\d+$', hostname):
        return False

    # Filtrar IDs de tickets Jira: icrd-141, s3-123, ngcs-456 (pero NO s3-node-123)
    if re.match(r'^[a-z]{2,6}-\d{1,5}$', hostname) and not hostname.startswith('s3-node'):
        return False

    # Filtrar nombres de imágenes adjuntas: image-2025-11-18, screenshot-1
    if re.match(r'^(image|screenshot|img|pic|photo)-', hostname):
        return False

    return True


def extract_hosts(text: str) -> List[str]:
    """Extrae hostnames del texto usando múltiples patrones."""
    if not text:
        return []

    text_lower = text.lower()
    all_matches = set()

    # Aplicar todos los patrones
    for pattern in HOST_PATTERNS:
        matches = pattern.findall(text_lower)
        all_matches.update(matches)

    # Filtrar falsos positivos
    valid_hosts = [h for h in all_matches if is_valid_host(h)]

    return list(set(valid_hosts))


def extract_technologies(text: str) -> List[str]:
    """Extrae tecnologías conocidas del texto."""
    if not text:
        return []
    text_lower = text.lower()
    found = []
    for tech in TECHNOLOGIES:
        if re.search(rf'\b{re.escape(tech)}\b', text_lower):
            found.append(tech)
    return list(set(found))


def is_valid_service_tag(tag: str) -> bool:
    """Valida si un tag entre corchetes es un servicio válido."""
    tag = tag.strip()
    if tag.startswith('~'):
        return False
    if re.match(r'\d{2}/\d{2}/\d{4}', tag):
        return False
    if tag.startswith('http') or '.com' in tag or '.org' in tag:
        return False
    if tag.startswith('!') or tag.endswith('!'):
        return False
    if len(tag) < 2:
        return False
    if tag.replace(' ', '').replace(':', '').replace(',', '').isdigit():
        return False
    return True


def parse_business_unit(bu: str) -> Optional[str]:
    """
    Parsea un Business Unit y extrae el nombre del servicio.

    Formatos soportados:
    - AR_Cloud Builder -> cloud builder
    - IC-S3 Object Storage -> s3 object storage
    - FH_Control Panel -> control panel
    - IONOS-NGCS -> ngcs
    - Strato-Mail -> mail
    - home.pl-Webmail -> webmail
    - ACS, Dave, Sedo -> acs, dave, sedo (directos)
    - IONOS Cloud/.../IC-S3 Object Storage -> s3 object storage (jerárquico)
    """
    if not bu:
        return None

    bu = bu.strip()
    bu_lower = bu.lower()

    # Patrones de prefijos conocidos (ordenados por especificidad)
    PREFIX_PATTERNS = [
        # Formato con underscore: AR_xxx, FH_xxx
        (r'^ar_(.+)$', None),
        (r'^fh_(.+)$', None),

        # Formato con guión: IC-xxx, IONOS-xxx, Strato-xxx
        (r'^ic-(.+)$', None),
        (r'^ionos-(.+)$', None),
        (r'^strato-(.+)$', None),
        (r'^home\.pl-(.+)$', None),

        # Formatos de otras marcas
        (r'^cronon[- ](.+)$', None),
        (r'^fasthosts[- ](.+)$', None),
        (r'^world4you[- ](.+)$', None),
        (r'^internetx[- ](.+)$', None),
        (r'^we22[- ](.+)$', None),
        (r'^udag[- ](.+)$', None),

        # Formato con paréntesis: Next Generation Cloud Server (NGCS)
        (r'^(.+?)\s*\(([A-Za-z]{2,10}(?:-[A-Za-z]{2,10})?)\)$', 2),
    ]

    for pattern, group_idx in PREFIX_PATTERNS:
        match = re.match(pattern, bu_lower)
        if match:
            if group_idx is not None:
                service = match.group(group_idx)
            else:
                service = match.group(1)
            return service.replace('_', ' ').strip()

    # Buscar formato jerárquico: "IONOS Cloud/IONOS Cloud PSS/IC-S3 Object Storage"
    if '/' in bu:
        parts = bu.split('/')
        last_part = parts[-1].strip()

        # Intentar parsear la última parte recursivamente
        parsed = parse_business_unit(last_part)
        if parsed:
            return parsed

        return last_part.lower()

    # Filtrar sufijos genéricos de sistemas
    GENERIC_SUFFIXES = [
        'business support systems', 'customer interaction systems',
        'employee support systems', 'operations support systems',
        'product service systems', 'external supplier systems',
        'outsourced service systems', 'corporate management systems',
        '-bss', '-cis', '-ess', '-oss', '-pss', '-extss', '-outss', '-cms',
    ]

    result = bu_lower
    for suffix in GENERIC_SUFFIXES:
        if result.endswith(suffix):
            result = result[:-len(suffix)].strip()
            result = re.sub(r'\s*\([^)]*\)\s*$', '', result).strip()
            break

    if result and len(result) >= 2:
        return result

    if len(bu) >= 2 and len(bu) <= 50:
        return bu_lower

    return None


def extract_services(text: str, business_units: List[str] = None) -> List[str]:
    """Extrae servicios del texto y business units."""
    services = set()
    IGNORE_TAGS = {
        'ai', 'dev', 'smb', 'urgent', 'qa', 'prod', 'pre', 'test',
        'wip', 'todo', 'done', 'blocked', 'review',
        'minor', 'major', 'critical', 'blocker',
        'bug', 'feature', 'task', 'story', 'epic',
    }

    if text:
        text_lower = text.lower()
        for canonical, aliases in SERVICE_SYNONYMS.items():
            if canonical in text_lower:
                services.add(canonical)
            for alias in aliases:
                if alias in text_lower:
                    services.add(canonical)

        tags = re.findall(r'\[([^\]]+)\]', text)
        for tag in tags:
            if not is_valid_service_tag(tag):
                continue
            tag_lower = tag.lower().strip()
            if tag_lower in IGNORE_TAGS:
                continue
            for canonical, aliases in SERVICE_SYNONYMS.items():
                if canonical in tag_lower or any(a in tag_lower for a in aliases):
                    services.add(canonical)
                    break

    if business_units:
        for bu in business_units:
            service = parse_business_unit(bu)
            if service:
                services.add(service)

    return list(services)


def extract_live_intervals(comments: List[Dict]) -> List[Dict[str, str]]:
    """Extrae intervalos de ejecución real de los comentarios."""
    intervals = []
    for comment in comments:
        body = comment.get('body', '')
        if not body:
            continue
        matches = INTERVAL_PATTERN.findall(body)
        for match in matches:
            start_date, start_time, end_date, end_time = match
            if not end_date:
                end_date = start_date
            start_iso = parse_interval_date(start_date, start_time)
            end_iso = parse_interval_date(end_date, end_time)
            if start_iso and end_iso:
                intervals.append({"start": start_iso, "end": end_iso})
    return intervals


def extract_timeline_entries(description: str) -> List[Dict]:
    """Extrae entradas del timeline de la descripción."""
    entries = []
    if not description:
        return entries
    matches = TIMELINE_PATTERN.findall(description)
    for match in matches:
        date_str, time_str, user, action = match
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y%m%d %H:%M")
            entries.append({
                "timestamp": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "user": user.lower(),
                "action": action.strip()
            })
        except:
            continue
    return entries


def extract_first_impact_time(description: str, timeline_entries: List[Dict]) -> Optional[str]:
    """Determina el momento del primer impacto."""
    if timeline_entries:
        return timeline_entries[0].get('timestamp')
    return None


def extract_people_involved(issue_data: Dict, comments: List[Dict], timeline_entries: List[Dict]) -> List[str]:
    """Extrae todas las personas involucradas."""
    people = set()

    assignee = issue_data.get('assignee')
    if assignee:
        name = assignee.get('name') if isinstance(assignee, dict) else safe_get(assignee, 'name')
        if name:
            people.add(name.lower())

    reporter = issue_data.get('reporter')
    if reporter:
        name = reporter.get('name') if isinstance(reporter, dict) else safe_get(reporter, 'name')
        if name:
            people.add(name.lower())

    for comment in comments:
        author = comment.get('author', '')
        if author:
            people.add(author.lower().replace(' ', ''))

    for entry in timeline_entries:
        user = entry.get('user', '')
        if user:
            people.add(user.lower())

    for field in ['tech_escalation', 'permitted_users', 'status_watchers']:
        value = issue_data.get(field)
        if isinstance(value, list):
            for item in value:
                name = item.get('name') if isinstance(item, dict) else None
                if name:
                    people.add(name.lower())

    return list(people)


def get_custom_field_value(fields, field_key: str):
    """Obtiene el valor de un campo custom."""
    jira_field = CUSTOM_FIELDS.get(field_key)
    if not jira_field:
        return None

    value = safe_get(fields, jira_field)

    if value is None:
        return None

    if hasattr(value, 'name'):
        return value.name
    if hasattr(value, 'value'):
        return value.value

    if isinstance(value, list):
        result = []
        for item in value:
            if hasattr(item, 'name'):
                result.append(item.name)
            elif hasattr(item, 'value'):
                result.append(item.value)
            elif isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                result.append(item.get('name') or item.get('value') or str(item))
        return result

    return value


# ══════════════════════════════════════════════════════════════════════════════
#  EXTRACTOR PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def extract_ticket(jira: JIRA, issue_key: str) -> Optional[Dict[str, Any]]:
    """Extrae y normaliza un ticket de Jira."""
    try:
        logger.info(f"Extracting: {issue_key}")
        issue = jira.issue(issue_key, expand='changelog')
        fields = issue.fields

        issue_type = safe_get(safe_get(fields, 'issuetype'), 'name', '')
        if 'incident' in issue_type.lower():
            ticket_type = "INCIDENT"
        elif 'change' in issue_type.lower():
            ticket_type = "CHANGE"
        else:
            ticket_type = issue_type.upper()

        comments = []
        try:
            for comment in jira.comments(issue_key):
                comments.append({
                    'id': comment.id,
                    'author': safe_get(safe_get(comment, 'author'), 'displayName', 'Unknown'),
                    'created': safe_get(comment, 'created'),
                    'body': safe_get(comment, 'body', '')
                })
        except Exception as e:
            logger.warning(f"Error extracting comments from {issue_key}: {e}")

        summary = safe_get(fields, 'summary', '')
        description = safe_get(fields, 'description', '')
        comments_text = ' '.join([c.get('body', '') for c in comments])
        full_text = f"{summary} {description} {comments_text}"

        timeline_entries = extract_timeline_entries(description)

        affected_bu = get_custom_field_value(fields, 'affected_business_units') or []
        if isinstance(affected_bu, str):
            affected_bu = [affected_bu]

        live_intervals = extract_live_intervals(comments)

        issue_data = {
            'assignee': {'name': safe_get(safe_get(fields, 'assignee'), 'name')},
            'reporter': {'name': safe_get(safe_get(fields, 'reporter'), 'name')},
            'tech_escalation': get_custom_field_value(fields, 'tech_escalation'),
            'permitted_users': get_custom_field_value(fields, 'permitted_users'),
        }

        warnings = []
        if ticket_type == "CHANGE" and not live_intervals:
            warnings.append("No live_intervals found in comments, using planned_start/end")

        normalized = {
            "issue_key": issue.key,
            "ticket_type": ticket_type,
            "summary": summary,
            "times": {
                "created_at": normalize_datetime(safe_get(fields, 'created')),
                "updated_at": normalize_datetime(safe_get(fields, 'updated')),
                "resolved_at": normalize_datetime(safe_get(fields, 'resolutiondate')),
                "first_impact_time": extract_first_impact_time(description, timeline_entries),
                "planned_start": normalize_datetime(get_custom_field_value(fields, 'start_datetime')),
                "planned_end": normalize_datetime(get_custom_field_value(fields, 'end_datetime')),
                "live_intervals": live_intervals,
            },
            "entities": {
                "services": extract_services(full_text, affected_bu),
                "hosts": extract_hosts(full_text),
                "technologies": extract_technologies(full_text),
            },
            "organization": {
                "team": get_custom_field_value(fields, 'responsible_entity'),
                "assignee": safe_get(safe_get(fields, 'assignee'), 'name'),
                "reporter": safe_get(safe_get(fields, 'reporter'), 'name'),
                "owner": get_custom_field_value(fields, 'change_owner') or get_custom_field_value(fields, 'incident_owner'),
                "people_involved": extract_people_involved(issue_data, comments, timeline_entries),
            },
            "classification": {
                "cause": get_custom_field_value(fields, 'cause'),
                "effect": get_custom_field_value(fields, 'effect'),
                "environments": get_custom_field_value(fields, 'environments') or [],
                "change_category": get_custom_field_value(fields, 'change_category'),
                "customer_impact": get_custom_field_value(fields, 'customer_impact'),
                "resolution": safe_get(safe_get(fields, 'resolution'), 'name'),
            },
            "raw_fields": {
                "labels": safe_get(fields, 'labels', []),
                "affected_business_units": affected_bu,
                "causing_business_units": get_custom_field_value(fields, 'causing_business_units'),
            },
            "_extraction": {
                "version": VERSION,
                "extracted_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source": "deterministic",
                "warnings": warnings,
                "timeline_entries_count": len(timeline_entries),
                "comments_count": len(comments),
            }
        }

        return normalized

    except Exception as e:
        logger.error(f"Error extracting {issue_key}: {e}")
        return None


def extract_ticket_with_retry(jira: JIRA, issue_key: str, progress_counter: dict, total: int) -> Optional[Dict[str, Any]]:
    """
    Extrae un ticket con retry automático en caso de rate limiting.
    Actualiza el contador de progreso de forma thread-safe.
    """
    for attempt in range(MAX_RETRIES):
        try:
            result = extract_ticket(jira, issue_key)

            # Actualizar progreso de forma thread-safe
            with progress_counter['lock']:
                progress_counter['done'] += 1

            return result

        except Exception as e:
            error_str = str(e).lower()

            # Detectar rate limiting (429) o errores de conexión
            if '429' in error_str or 'rate' in error_str or 'too many' in error_str:
                wait_time = RETRY_DELAY_BASE * (2 ** attempt)
                logger.warning(f"Rate limit en {issue_key}, reintentando en {wait_time}s (intento {attempt + 1}/{MAX_RETRIES})")
                time.sleep(wait_time)
            elif attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY_BASE * (attempt + 1)
                logger.warning(f"Error en {issue_key}: {e}. Reintentando en {wait_time}s (intento {attempt + 1}/{MAX_RETRIES})")
                time.sleep(wait_time)
            else:
                logger.error(f"Error definitivo extrayendo {issue_key} tras {MAX_RETRIES} intentos: {e}")

                # Actualizar progreso incluso en error
                with progress_counter['lock']:
                    progress_counter['done'] += 1
                    progress_counter['errors'] += 1

                return None

    return None


class SearchOptions:
    """Opciones de búsqueda de TECCMs."""
    def __init__(
        self,
        window_before: str = "48h",
        window_after: str = "2h",
        include_active: bool = True,
        include_no_end: bool = True,
        max_results: int = 500,
        extra_jql: str = "",
        project: str = "TECCM"
    ):
        self.window_before = parse_window(window_before)
        self.window_after = parse_window(window_after)
        self.include_active = include_active
        self.include_no_end = include_no_end
        self.max_results = max_results
        self.extra_jql = extra_jql.strip()
        self.project = project


def search_teccm_in_window(
    jira: JIRA,
    inc_created: str,
    window: timedelta = None,
    options: SearchOptions = None
) -> List[str]:
    """
    Busca TECCMs relevantes para un incidente.

    Realiza hasta tres búsquedas configurables:
    1. TECCMs que EMPEZARON en la ventana temporal
    2. TECCMs que ESTABAN ACTIVOS al momento del incidente (opcional)
    3. TECCMs sin fecha fin (opcional)

    Args:
        jira: Cliente JIRA conectado
        inc_created: Fecha de creación del INC en formato ISO
        window: Ventana temporal (legacy, se ignora si options está presente)
        options: Opciones avanzadas de búsqueda

    Returns:
        Lista de keys de TECCMs encontrados (sin duplicados)
    """
    # Usar opciones por defecto si no se proporcionan
    if options is None:
        options = SearchOptions(
            window_before=f"{int(window.total_seconds() // 3600)}h" if window else "48h"
        )

    all_teccm_keys = set()
    search_stats = {
        "window": 0,
        "active": 0,
        "no_end": 0,
    }

    try:
        inc_dt = datetime.strptime(inc_created[:19], "%Y-%m-%dT%H:%M:%S")
        inc_str = inc_dt.strftime("%Y-%m-%d %H:%M")

        # Construir filtro JQL adicional
        extra_filter = f" {options.extra_jql}" if options.extra_jql else ""

        # ══════════════════════════════════════════════════════════════════════
        # BÚSQUEDA 1: TECCMs que empezaron en la ventana temporal
        # ══════════════════════════════════════════════════════════════════════
        start_dt = inc_dt - options.window_before
        end_dt = inc_dt + options.window_after

        start_str = start_dt.strftime("%Y-%m-%d %H:%M")
        end_str = end_dt.strftime("%Y-%m-%d %H:%M")

        jql_window = (
            f'project = {options.project} AND '
            f'"Start Date/Time" >= "{start_str}" AND '
            f'"Start Date/Time" <= "{end_str}"'
            f'{extra_filter} '
            f'ORDER BY "Start Date/Time" DESC'
        )

        logger.info(f"Búsqueda 1 - TECCMs en ventana: {jql_window}")
        issues_window = jira.search_issues(jql_window, maxResults=options.max_results)
        window_keys = [issue.key for issue in issues_window]
        all_teccm_keys.update(window_keys)
        search_stats["window"] = len(window_keys)
        logger.info(f"  → Encontrados {len(window_keys)} TECCMs en ventana")

        # ══════════════════════════════════════════════════════════════════════
        # BÚSQUEDA 2: TECCMs activos al momento del incidente (opcional)
        # ══════════════════════════════════════════════════════════════════════
        if options.include_active:
            jql_active = (
                f'project = {options.project} AND '
                f'"Start Date/Time" <= "{inc_str}" AND '
                f'"End Date/Time" >= "{inc_str}"'
                f'{extra_filter} '
                f'ORDER BY "Start Date/Time" DESC'
            )

            logger.info(f"Búsqueda 2 - TECCMs activos: {jql_active}")
            issues_active = jira.search_issues(jql_active, maxResults=options.max_results)
            active_keys = [issue.key for issue in issues_active]
            new_from_active = [k for k in active_keys if k not in all_teccm_keys]
            all_teccm_keys.update(active_keys)
            search_stats["active"] = len(new_from_active)
            logger.info(f"  → Encontrados {len(active_keys)} TECCMs activos ({len(new_from_active)} nuevos)")
        else:
            logger.info("Búsqueda 2 - TECCMs activos: OMITIDA")

        # ══════════════════════════════════════════════════════════════════════
        # BÚSQUEDA 3: TECCMs activos sin fecha fin (opcional)
        # ══════════════════════════════════════════════════════════════════════
        if options.include_no_end:
            jql_no_end = (
                f'project = {options.project} AND '
                f'"Start Date/Time" <= "{inc_str}" AND '
                f'"End Date/Time" IS EMPTY'
                f'{extra_filter} '
                f'ORDER BY "Start Date/Time" DESC'
            )

            logger.info(f"Búsqueda 3 - TECCMs sin fecha fin: {jql_no_end}")
            issues_no_end = jira.search_issues(jql_no_end, maxResults=options.max_results)
            no_end_keys = [issue.key for issue in issues_no_end]
            new_from_no_end = [k for k in no_end_keys if k not in all_teccm_keys]
            all_teccm_keys.update(no_end_keys)
            search_stats["no_end"] = len(new_from_no_end)
            logger.info(f"  → Encontrados {len(no_end_keys)} TECCMs sin fecha fin ({len(new_from_no_end)} nuevos)")
        else:
            logger.info("Búsqueda 3 - TECCMs sin fecha fin: OMITIDA")

        logger.info(f"Total TECCMs únicos: {len(all_teccm_keys)} (ventana: {search_stats['window']}, activos: +{search_stats['active']}, sin fin: +{search_stats['no_end']})")
        return list(all_teccm_keys)

    except Exception as e:
        logger.error(f"Error searching TECCMs: {e}")
        return list(all_teccm_keys) if all_teccm_keys else []


# ══════════════════════════════════════════════════════════════════════════════
#  API DE ALTO NIVEL
# ══════════════════════════════════════════════════════════════════════════════

def extract_tickets_parallel(
    jira: JIRA,
    ticket_keys: List[str],
    num_threads: int,
    progress_callback: Callable[[int, int], None] = None
) -> List[Dict[str, Any]]:
    """
    Extrae múltiples tickets en paralelo usando ThreadPoolExecutor.

    Args:
        jira: Cliente JIRA conectado
        ticket_keys: Lista de keys de tickets a extraer
        num_threads: Número de hilos a usar
        progress_callback: Función callback(current, total) para reportar progreso

    Returns:
        Lista de tickets extraídos
    """
    results = []
    total = len(ticket_keys)

    if total == 0:
        return results

    # Contador de progreso thread-safe
    progress_counter = {
        'done': 0,
        'errors': 0,
        'lock': threading.Lock()
    }

    logger.info(f"Extracting {total} tickets with {num_threads} threads...")

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        # Lanzar todas las tareas
        future_to_key = {
            executor.submit(extract_ticket_with_retry, jira, key, progress_counter, total): key
            for key in ticket_keys
        }

        # Recoger resultados a medida que terminan
        for future in as_completed(future_to_key):
            ticket_key = future_to_key[future]
            try:
                result = future.result()
                if result:
                    results.append(result)

                # Llamar al callback de progreso
                if progress_callback:
                    with progress_counter['lock']:
                        progress_callback(progress_counter['done'], total)

            except Exception as e:
                logger.error(f"Unexpected exception extracting {ticket_key}: {e}")

    errors = progress_counter['errors']
    if errors > 0:
        logger.warning(f"Completed with {errors} errors out of {total} tickets")

    return results


def extract_inc_with_teccms(
    jira: JIRA,
    inc_key: str,
    window_str: str = "48h",
    progress_callback: Callable[[int, int], None] = None,
    num_threads: int = DEFAULT_THREADS,
    search_options: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Extrae un INC y todos los TECCMs en la ventana temporal.

    Args:
        jira: Cliente JIRA conectado
        inc_key: Key del incidente (e.g., "INC-117346")
        window_str: Ventana temporal legacy (e.g., "48h", "2d") - se ignora si search_options está presente
        progress_callback: Función callback(current, total) para reportar progreso
        num_threads: Número de hilos para extracción paralela (default: 8)
        search_options: Dict con opciones avanzadas de búsqueda:
            - window_before: str (default "48h")
            - window_after: str (default "2h")
            - include_active: bool (default True)
            - include_no_end: bool (default True)
            - max_results: int (default 500)
            - extra_jql: str (default "")
            - project: str (default "TECCM")

    Returns:
        Dict con extraction_info y tickets
    """
    inc_key = inc_key.upper()

    # Construir opciones de búsqueda
    if search_options:
        # Importante: usar 'is not None' para no confundir False con ausencia de valor
        include_active = search_options.get("include_active")
        include_no_end = search_options.get("include_no_end")

        options = SearchOptions(
            window_before=search_options.get("window_before", "48h"),
            window_after=search_options.get("window_after", "2h"),
            include_active=include_active if include_active is not None else True,
            include_no_end=include_no_end if include_no_end is not None else True,
            max_results=search_options.get("max_results", 500),
            extra_jql=search_options.get("extra_jql", ""),
            project=search_options.get("project", "TECCM"),
        )
        # Para el log, usar window_before como referencia
        window_str = search_options.get("window_before", "48h")
    else:
        options = SearchOptions(window_before=window_str)

    # Extraer el INC primero (siempre secuencial, necesitamos la fecha)
    logger.info(f"Extracting INC to determine time window...")
    inc_data = extract_ticket(jira, inc_key)

    if not inc_data:
        raise ValueError(f"Could not extract incident {inc_key}")

    # Buscar TECCMs en la ventana
    inc_created = inc_data['times']['created_at']

    logger.info(f"Searching TECCMs with options: window_before={window_str}, include_active={options.include_active}, include_no_end={options.include_no_end}")
    teccm_keys = search_teccm_in_window(jira, inc_created, options=options)

    logger.info(f"Found {len(teccm_keys)} TECCMs")

    # Reportar progreso inicial (INC ya extraído)
    total = 1 + len(teccm_keys)
    if progress_callback:
        progress_callback(1, total)

    # Extraer TECCMs en paralelo
    results = [inc_data]  # Ya tenemos el INC

    if teccm_keys:
        # Ajustar número de hilos (no más que tickets)
        actual_threads = min(num_threads, len(teccm_keys))

        # Wrapper para el callback que ajusta el offset (ya tenemos 1 extraído)
        def adjusted_callback(current, total_teccms):
            if progress_callback:
                progress_callback(1 + current, total)

        teccm_results = extract_tickets_parallel(
            jira,
            teccm_keys,
            actual_threads,
            adjusted_callback
        )
        results.extend(teccm_results)

    # Progreso final
    if progress_callback:
        progress_callback(total, total)

    logger.info(f"Extracted {len(results)} tickets ({len(results) - 1} TECCMs) using {min(num_threads, max(1, len(teccm_keys)))} threads")

    # Información de extracción incluyendo opciones usadas
    extraction_info = {
        "version": VERSION,
        "extracted_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_tickets": len(results),
        "source_mode": "inc+window",
        "inc_key": inc_key,
        "window": window_str,
        "threads_used": min(num_threads, max(1, len(teccm_keys))),
    }

    # Añadir opciones avanzadas si se usaron
    if search_options:
        extraction_info["search_options"] = {
            "window_before": search_options.get("window_before", "48h"),
            "window_after": search_options.get("window_after", "2h"),
            "include_active": options.include_active,
            "include_no_end": options.include_no_end,
            "max_results": options.max_results,
            "extra_jql": options.extra_jql or None,
            "project": options.project,
        }

    return {
        "extraction_info": extraction_info,
        "tickets": results
    }
