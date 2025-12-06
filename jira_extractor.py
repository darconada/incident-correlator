#!/usr/bin/env python3
"""
Extractor determinista de tickets Jira.
Genera JSON normalizado para el sistema de scoring INC ↔ TECCM.

Uso:
  # Modo 1: Extraer un solo ticket
  python jira_extractor.py --ticket INC-117346

  # Modo 2: Extraer un INC + todos los TECCM en ventana temporal
  python jira_extractor.py --inc INC-117346 --window 48h

  # Modo 3: Extraer una lista de tickets desde fichero
  python jira_extractor.py --from-file tickets.txt

  # Modo 4: Query JQL directa
  python jira_extractor.py --jql "project = TECCM AND created >= -48h"

Opciones comunes:
  --user          Usuario de Jira
  --password      Password de Jira
  --output        Fichero de salida JSON
  --output-dir    Directorio para salida
  --threads       Número de hilos para extracción paralela (default: 8)
"""

import os
import sys
import re
import json
import argparse
import getpass
import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from jira import JIRA
except ImportError:
    print("Error: Librería 'jira' no instalada.")
    print("Instálala con: pip install jira")
    sys.exit(1)

# ── Configuración ────────────────────────────────────────────────────────────
JIRA_URL = "https://hosting-jira.1and1.org"
VERSION = "1.1"

# Configuración de paralelización
DEFAULT_THREADS = 8
MAX_RETRIES = 3
RETRY_DELAY_BASE = 2  # segundos, se multiplica exponencialmente

# ── Logger ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

# ── Mapeo de campos custom de Jira ───────────────────────────────────────────
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

# ── Diccionarios para extracción determinista ────────────────────────────────
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
    "kubernetes": ["k8s", "container registry", "ic-kubernetes", "keycloak"],  # keycloak suele correr en k8s
}

# Grupos de servicios relacionados (mismo ecosistema = match parcial)
# Se usa para dar puntos parciales cuando los servicios no son idénticos pero están relacionados
RELATED_SERVICE_GROUPS = {
    "ionos-cloud": [
        "ic-cis", "ic-sre", "ic-oss", "ic-pss", "ic-bss", "ic-ess",
        "cloud api", "dcd", "dcd api", "compute", "network", "block storage",
        "s3 object storage", "kubernetes", "sre", "iam",
    ],
    "arsys": [
        "customer area", "control panel", "mail", "dns", "webhosting",
        "dedicated server", "cloud server",
    ],
}

# ── Regex patterns ───────────────────────────────────────────────────────────
# Hosts: múltiples patrones comunes en infraestructura
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

# Patrones para filtrar falsos positivos (UUIDs, hashes, etc)
UUID_FRAGMENT_PATTERN = re.compile(r'^[a-f0-9]{4,8}$', re.IGNORECASE)
HEX_HASH_PATTERN = re.compile(r'^[a-f0-9]{32,}$', re.IGNORECASE)

# Palabras que no son hosts aunque matcheen el patrón
HOST_BLACKLIST = {
    'https', 'http', 'image', 'browse', 'version', 'update', 'release',
    'node12', 'node10', 'node11', 'node-33', 'node-91', 'node-601', 'node-604', 'node-901',  # Fragmentos de s3-node-*
    'utf8', 'utf16', 'iso8859', 'win1252',  # Encodings
    'amd64', 'x86', 'arm64',  # Arquitecturas
    'eu-south-2', 'eu-central-1', 'eu-central-2', 'us-east-1', 'us-west-2',  # Regiones AWS/Cloud
    'region', 'regions',
    # Nombres de imágenes adjuntas en Jira
    'image-2025', 'image-2024', 'image-2023', 'screenshot-1', 'screenshot-2',
}

# Intervalos en formato [DD/MM/YYYY HH:MM, DD/MM/YYYY HH:MM] o [DD/MM/YYYY HH:MM, HH:MM]
INTERVAL_PATTERN = re.compile(
    r'\[(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}),\s*(?:(\d{2}/\d{2}/\d{4})\s+)?(\d{2}:\d{2})\]'
)

# Timeline en descripción: YYYYMMDD HH:MM - usuario: acción
TIMELINE_PATTERN = re.compile(
    r'^(\d{8})\s+(\d{2}:\d{2})\s*-\s*(\w+):\s*(.+)$',
    re.MULTILINE
)

# Referencias a otros tickets
TICKET_REF_PATTERN = re.compile(r'\b((?:INC|TECCM|PROB|ADAPPWEB|GPHARTPODS)-\d+)\b')


# ── Funciones de utilidad ────────────────────────────────────────────────────

def get_credentials_interactive() -> Tuple[str, str]:
    """Pide usuario y password de forma interactiva."""
    print("\n" + "="*50)
    print("  AUTENTICACIÓN JIRA")
    print("="*50)
    
    user = input("Usuario: ").strip()
    if not user:
        print("Error: El usuario no puede estar vacío")
        sys.exit(1)
    
    password = getpass.getpass("Password: ").strip()
    if not password:
        print("Error: El password no puede estar vacío")
        sys.exit(1)
    
    return user, password


def conectar_jira(user: str, password: str) -> JIRA:
    """Establece conexión con Jira."""
    try:
        jira = JIRA(server=JIRA_URL, basic_auth=(user, password))
        logging.info("Conectado a Jira: %s como %s", JIRA_URL, user)
        return jira
    except Exception as e:
        logging.exception("Error conectando a Jira: %s", e)
        sys.exit(1)


def safe_get(obj, attr, default=None):
    """Obtiene un atributo de forma segura."""
    if obj is None:
        return default
    return getattr(obj, attr, default) if hasattr(obj, attr) else default


def parse_window(window_str: str) -> timedelta:
    """Parsea una ventana temporal como '48h', '2d', '120m'."""
    match = re.match(r'^(\d+)([hdm])$', window_str.lower())
    if not match:
        raise ValueError(f"Formato de ventana inválido: {window_str}. Usa formato como '48h', '2d', '120m'")
    
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
        # Jira format: 2025-07-22T10:30:50.227+0000
        dt = datetime.strptime(dt_str[:19], "%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except:
        return dt_str


def parse_interval_date(date_str: str, time_str: str, reference_date: str = None) -> Optional[str]:
    """Parsea fecha y hora de un intervalo a ISO format."""
    try:
        if date_str:
            # DD/MM/YYYY
            dt = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
        elif reference_date:
            # Solo hora, usar fecha de referencia
            ref = datetime.strptime(reference_date, "%d/%m/%Y")
            time = datetime.strptime(time_str, "%H:%M")
            dt = ref.replace(hour=time.hour, minute=time.minute)
        else:
            return None
        
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except:
        return None


# ── Extractores específicos ──────────────────────────────────────────────────

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
    # "node-33" es fragmento, "s3-node-33" es válido
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
        # Buscar como palabra completa
        if re.search(rf'\b{re.escape(tech)}\b', text_lower):
            found.append(tech)
    
    return list(set(found))


def is_valid_service_tag(tag: str) -> bool:
    """Valida si un tag entre corchetes es un servicio válido (no fecha, no mention, etc)."""
    tag = tag.strip()
    
    # Filtrar mentions de Jira: [~username]
    if tag.startswith('~'):
        return False
    
    # Filtrar intervalos de fechas: [22/07/2025 07:03, 22/07/2025 13:18]
    if re.match(r'\d{2}/\d{2}/\d{4}', tag):
        return False
    
    # Filtrar URLs
    if tag.startswith('http') or '.com' in tag or '.org' in tag:
        return False
    
    # Filtrar imágenes de Jira: !image.png!
    if tag.startswith('!') or tag.endswith('!'):
        return False
    
    # Filtrar tags muy cortos (menos de 2 caracteres)
    if len(tag) < 2:
        return False
    
    # Filtrar tags que son solo números
    if tag.replace(' ', '').replace(':', '').replace(',', '').isdigit():
        return False
    
    return True


def extract_services(text: str, business_units: List[str] = None) -> List[str]:
    """Extrae servicios del texto y business units."""
    services = set()
    
    # Tags comunes que NO son servicios
    IGNORE_TAGS = {
        'ai', 'dev', 'smb', 'urgent', 'qa', 'prod', 'pre', 'test',
        'wip', 'todo', 'done', 'blocked', 'review',
        'minor', 'major', 'critical', 'blocker',
        'bug', 'feature', 'task', 'story', 'epic',
    }
    
    if text:
        text_lower = text.lower()
        
        # Buscar servicios conocidos y sus sinónimos
        for canonical, aliases in SERVICE_SYNONYMS.items():
            if canonical in text_lower:
                services.add(canonical)
            for alias in aliases:
                if alias in text_lower:
                    services.add(canonical)
        
        # Buscar en tags del summary: [AI][Customer system]
        tags = re.findall(r'\[([^\]]+)\]', text)
        for tag in tags:
            # Validar que es un tag de servicio válido
            if not is_valid_service_tag(tag):
                continue
            
            tag_lower = tag.lower().strip()
            
            # Ignorar tags comunes que no son servicios
            if tag_lower in IGNORE_TAGS:
                continue
            
            # Buscar si matchea algún sinónimo conocido
            matched = False
            for canonical, aliases in SERVICE_SYNONYMS.items():
                if canonical in tag_lower or any(a in tag_lower for a in aliases):
                    services.add(canonical)
                    matched = True
                    break
            
            # Si no matchea ningún sinónimo conocido, NO añadir automáticamente
            # (evita añadir basura como tags genéricos)
    
    # Extraer de business units con múltiples formatos
    if business_units:
        for bu in business_units:
            service = parse_business_unit(bu)
            if service:
                services.add(service)
    
    return list(services)


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
        
        # Formato con paréntesis: Next Generation Cloud Server (NGCS), Customer Interaction Systems (IC-CIS)
        (r'^(.+?)\s*\(([A-Za-z]{2,10}(?:-[A-Za-z]{2,10})?)\)$', 2),  # Captura el acrónimo (permite IC-CIS)
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
        # Tomar la última parte de la jerarquía
        parts = bu.split('/')
        last_part = parts[-1].strip()
        
        # Intentar parsear la última parte recursivamente
        parsed = parse_business_unit(last_part)
        if parsed:
            return parsed
        
        # Si no matchea ningún patrón, usar la última parte tal cual
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
            # Quitar paréntesis sobrantes
            result = re.sub(r'\s*\([^)]*\)\s*$', '', result).strip()
            break
    
    # Si quedó algo útil después de quitar sufijos
    if result and len(result) >= 2:
        return result
    
    # Valor directo sin transformar (ACS, Dave, Sedo, etc.)
    if len(bu) >= 2 and len(bu) <= 50:
        return bu_lower
    
    return None


def extract_live_intervals(comments: List[Dict]) -> List[Dict[str, str]]:
    """Extrae intervalos de ejecución real de los comentarios."""
    intervals = []
    
    for comment in comments:
        body = comment.get('body', '')
        if not body:
            continue
        
        # Buscar intervalos en formato [DD/MM/YYYY HH:MM, DD/MM/YYYY HH:MM]
        matches = INTERVAL_PATTERN.findall(body)
        
        for match in matches:
            start_date, start_time, end_date, end_time = match
            
            # Si no hay fecha final, usar la misma que la inicial
            if not end_date:
                end_date = start_date
            
            start_iso = parse_interval_date(start_date, start_time)
            end_iso = parse_interval_date(end_date, end_time)
            
            if start_iso and end_iso:
                intervals.append({
                    "start": start_iso,
                    "end": end_iso
                })
    
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
            # YYYYMMDD -> datetime
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
    # Si hay timeline, el primer entry es el first impact
    if timeline_entries:
        return timeline_entries[0].get('timestamp')
    
    return None


def extract_people_involved(issue_data: Dict, comments: List[Dict], timeline_entries: List[Dict]) -> List[str]:
    """Extrae todas las personas involucradas."""
    people = set()
    
    # Assignee y reporter
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
    
    # De los comentarios
    for comment in comments:
        author = comment.get('author', '')
        if author:
            # Normalizar: "Pablo Arraiz Aransay" -> intentar extraer username
            people.add(author.lower().replace(' ', ''))
    
    # Del timeline
    for entry in timeline_entries:
        user = entry.get('user', '')
        if user:
            people.add(user.lower())
    
    # De campos custom (tech escalation, permitted users, etc.)
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
    
    # Si es un objeto con 'name' o 'value'
    if hasattr(value, 'name'):
        return value.name
    if hasattr(value, 'value'):
        return value.value
    
    # Si es una lista
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
    
    # Si es string u otro tipo básico
    return value


# ── Extractor principal ──────────────────────────────────────────────────────

def extract_ticket(jira: JIRA, issue_key: str) -> Optional[Dict[str, Any]]:
    """Extrae y normaliza un ticket de Jira."""
    
    try:
        logging.info("Extrayendo: %s", issue_key)
        issue = jira.issue(issue_key, expand='changelog')
        fields = issue.fields
        
        # Determinar tipo de ticket
        issue_type = safe_get(safe_get(fields, 'issuetype'), 'name', '')
        if 'incident' in issue_type.lower():
            ticket_type = "INCIDENT"
        elif 'change' in issue_type.lower():
            ticket_type = "CHANGE"
        else:
            ticket_type = issue_type.upper()
        
        # Extraer comentarios
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
            logging.warning("Error extrayendo comentarios de %s: %s", issue_key, e)
        
        # Construir texto completo para extracción de entidades
        summary = safe_get(fields, 'summary', '')
        description = safe_get(fields, 'description', '')
        comments_text = ' '.join([c.get('body', '') for c in comments])
        full_text = f"{summary} {description} {comments_text}"
        
        # Extraer timeline de la descripción
        timeline_entries = extract_timeline_entries(description)
        
        # Extraer business units para servicios
        affected_bu = get_custom_field_value(fields, 'affected_business_units') or []
        if isinstance(affected_bu, str):
            affected_bu = [affected_bu]
        
        # Extraer intervalos de ejecución de comentarios (para TECCM)
        live_intervals = extract_live_intervals(comments)
        
        # Preparar datos intermedios para people_involved
        issue_data = {
            'assignee': {'name': safe_get(safe_get(fields, 'assignee'), 'name')},
            'reporter': {'name': safe_get(safe_get(fields, 'reporter'), 'name')},
            'tech_escalation': get_custom_field_value(fields, 'tech_escalation'),
            'permitted_users': get_custom_field_value(fields, 'permitted_users'),
        }
        
        # Warnings para campos que requieren atención
        warnings = []
        if ticket_type == "CHANGE" and not live_intervals:
            warnings.append("No se encontraron live_intervals en comentarios, usando planned_start/end")
        
        # Construir JSON normalizado
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
        logging.error("Error extrayendo %s: %s", issue_key, e)
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
                done = progress_counter['done']
                
                # Mostrar progreso cada 10 tickets o al final
                if done % 10 == 0 or done == total:
                    pct = (done / total) * 100
                    print(f"\r  Progreso: {done}/{total} ({pct:.1f}%)", end='', flush=True)
            
            return result
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Detectar rate limiting (429) o errores de conexión
            if '429' in error_str or 'rate' in error_str or 'too many' in error_str:
                wait_time = RETRY_DELAY_BASE * (2 ** attempt)
                logging.warning("Rate limit en %s, reintentando en %ds (intento %d/%d)", 
                               issue_key, wait_time, attempt + 1, MAX_RETRIES)
                time.sleep(wait_time)
            elif attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY_BASE * (attempt + 1)
                logging.warning("Error en %s: %s. Reintentando en %ds (intento %d/%d)", 
                               issue_key, e, wait_time, attempt + 1, MAX_RETRIES)
                time.sleep(wait_time)
            else:
                logging.error("Error definitivo extrayendo %s tras %d intentos: %s", 
                             issue_key, MAX_RETRIES, e)
                
                # Actualizar progreso incluso en error
                with progress_counter['lock']:
                    progress_counter['done'] += 1
                    progress_counter['errors'] += 1
                
                return None
    
    return None


def extract_tickets_parallel(jira: JIRA, ticket_keys: List[str], num_threads: int) -> List[Dict[str, Any]]:
    """
    Extrae múltiples tickets en paralelo usando ThreadPoolExecutor.
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
    
    print(f"\n  Extrayendo {total} tickets con {num_threads} hilos...")
    
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
            except Exception as e:
                logging.error("Excepción inesperada en %s: %s", ticket_key, e)
    
    print()  # Nueva línea después del progreso
    
    errors = progress_counter['errors']
    if errors > 0:
        logging.warning("Completado con %d errores de %d tickets", errors, total)
    
    return results


def search_teccm_in_window(jira: JIRA, inc_created: str, window: timedelta) -> List[str]:
    """
    Busca TECCMs relevantes para un incidente.
    
    Realiza dos búsquedas:
    1. TECCMs que EMPEZARON en la ventana temporal (ej: últimas 48h)
    2. TECCMs que ESTABAN ACTIVOS al momento del incidente (cambios largos en curso)
    
    Combina ambos resultados sin duplicados.
    """
    
    all_teccm_keys = set()
    
    try:
        # Parsear fecha del incidente
        inc_dt = datetime.strptime(inc_created[:19], "%Y-%m-%dT%H:%M:%S")
        inc_str = inc_dt.strftime("%Y-%m-%d %H:%M")
        
        # ══════════════════════════════════════════════════════════════════════
        # BÚSQUEDA 1: TECCMs que empezaron en la ventana temporal
        # ══════════════════════════════════════════════════════════════════════
        start_dt = inc_dt - window
        end_dt = inc_dt + timedelta(hours=2)  # Pequeño margen después
        
        start_str = start_dt.strftime("%Y-%m-%d %H:%M")
        end_str = end_dt.strftime("%Y-%m-%d %H:%M")
        
        jql_window = (
            f'project = TECCM AND '
            f'"Start Date/Time" >= "{start_str}" AND '
            f'"Start Date/Time" <= "{end_str}" '
            f'ORDER BY "Start Date/Time" DESC'
        )
        
        logging.info("Búsqueda 1 - TECCMs en ventana: %s", jql_window)
        
        issues_window = jira.search_issues(jql_window, maxResults=500)
        window_keys = [issue.key for issue in issues_window]
        all_teccm_keys.update(window_keys)
        
        logging.info("  → Encontrados %d TECCMs en ventana de %s", len(window_keys), window)
        
        # ══════════════════════════════════════════════════════════════════════
        # BÚSQUEDA 2: TECCMs activos al momento del incidente
        # (empezaron ANTES del incidente y terminan DESPUÉS o no han terminado)
        # ══════════════════════════════════════════════════════════════════════
        jql_active = (
            f'project = TECCM AND '
            f'"Start Date/Time" <= "{inc_str}" AND '
            f'"End Date/Time" >= "{inc_str}" '
            f'ORDER BY "Start Date/Time" DESC'
        )
        
        logging.info("Búsqueda 2 - TECCMs activos: %s", jql_active)
        
        issues_active = jira.search_issues(jql_active, maxResults=500)
        active_keys = [issue.key for issue in issues_active]
        
        # Contar nuevos (no duplicados)
        new_from_active = [k for k in active_keys if k not in all_teccm_keys]
        all_teccm_keys.update(active_keys)
        
        logging.info("  → Encontrados %d TECCMs activos (%d nuevos)", len(active_keys), len(new_from_active))
        
        # ══════════════════════════════════════════════════════════════════════
        # BÚSQUEDA 3: TECCMs activos sin fecha fin (aún en curso)
        # ══════════════════════════════════════════════════════════════════════
        jql_no_end = (
            f'project = TECCM AND '
            f'"Start Date/Time" <= "{inc_str}" AND '
            f'"End Date/Time" IS EMPTY '
            f'ORDER BY "Start Date/Time" DESC'
        )
        
        logging.info("Búsqueda 3 - TECCMs sin fecha fin: %s", jql_no_end)
        
        issues_no_end = jira.search_issues(jql_no_end, maxResults=500)
        no_end_keys = [issue.key for issue in issues_no_end]
        
        new_from_no_end = [k for k in no_end_keys if k not in all_teccm_keys]
        all_teccm_keys.update(no_end_keys)
        
        logging.info("  → Encontrados %d TECCMs sin fecha fin (%d nuevos)", len(no_end_keys), len(new_from_no_end))
        
        # ══════════════════════════════════════════════════════════════════════
        logging.info("Total TECCMs únicos: %d", len(all_teccm_keys))
        
        return list(all_teccm_keys)
        
    except Exception as e:
        logging.error("Error buscando TECCMs: %s", e)
        return list(all_teccm_keys) if all_teccm_keys else []


def load_tickets_from_file(filepath: str) -> List[str]:
    """Carga lista de tickets desde un fichero."""
    tickets = []
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                # Extraer tickets de la línea (puede haber varios)
                found = TICKET_REF_PATTERN.findall(line)
                tickets.extend(found)
    
    return list(set(tickets))


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Extractor determinista de tickets Jira",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  %(prog)s --ticket INC-117346
  %(prog)s --inc INC-117346 --window 48h
  %(prog)s --from-file tickets.txt
  %(prog)s --jql "project = TECCM AND created >= -7d"
        """
    )
    
    # Modos de entrada (mutuamente excluyentes)
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--ticket", help="Extraer un solo ticket")
    mode_group.add_argument("--inc", help="Extraer INC + TECCMs en ventana (requiere --window)")
    mode_group.add_argument("--from-file", help="Fichero con lista de tickets")
    mode_group.add_argument("--jql", help="Query JQL directa")
    
    # Opciones adicionales
    parser.add_argument("--window", default="48h", help="Ventana temporal para buscar TECCMs (default: 48h)")
    parser.add_argument("--threads", "-t", type=int, default=DEFAULT_THREADS, 
                        help=f"Número de hilos para extracción paralela (default: {DEFAULT_THREADS})")
    parser.add_argument("--user", help="Usuario de Jira")
    parser.add_argument("--password", help="Password de Jira")
    parser.add_argument("--output", "-o", help="Fichero de salida JSON")
    parser.add_argument("--output-dir", help="Directorio para salida")
    
    args = parser.parse_args()
    
    # Obtener credenciales
    user = args.user
    password = args.password
    
    if not user or not password:
        user, password = get_credentials_interactive()
    
    # Conectar a Jira
    jira = conectar_jira(user, password)
    
    # Determinar qué tickets extraer
    tickets_to_extract = []
    
    if args.ticket:
        tickets_to_extract = [args.ticket.upper()]
    
    elif args.inc:
        inc_key = args.inc.upper()
        tickets_to_extract = [inc_key]
        
        # Extraer el INC primero para obtener su fecha
        logging.info("Extrayendo INC para determinar ventana temporal...")
        inc_data = extract_ticket(jira, inc_key)
        
        if inc_data:
            inc_created = inc_data['times']['created_at']
            window = parse_window(args.window)
            
            logging.info("Buscando TECCMs en ventana de %s antes de %s", args.window, inc_created)
            teccm_keys = search_teccm_in_window(jira, inc_created, window)
            
            logging.info("Encontrados %d TECCMs en la ventana", len(teccm_keys))
            tickets_to_extract.extend(teccm_keys)
    
    elif args.from_file:
        tickets_to_extract = load_tickets_from_file(args.from_file)
        logging.info("Cargados %d tickets desde %s", len(tickets_to_extract), args.from_file)
    
    elif args.jql:
        logging.info("Ejecutando JQL: %s", args.jql)
        try:
            issues = jira.search_issues(args.jql, maxResults=500)
            tickets_to_extract = [issue.key for issue in issues]
            logging.info("Encontrados %d tickets", len(tickets_to_extract))
        except Exception as e:
            logging.error("Error ejecutando JQL: %s", e)
            sys.exit(1)
    
    # Extraer todos los tickets
    results = []
    
    if len(tickets_to_extract) == 1:
        # Un solo ticket: extracción directa
        normalized = extract_ticket(jira, tickets_to_extract[0])
        if normalized:
            results.append(normalized)
    else:
        # Múltiples tickets: extracción paralela
        num_threads = min(args.threads, len(tickets_to_extract))  # No más hilos que tickets
        results = extract_tickets_parallel(jira, tickets_to_extract, num_threads)
    
    logging.info("Extraídos %d tickets de %d", len(results), len(tickets_to_extract))
    
    # Generar salida
    output_data = {
        "extraction_info": {
            "version": VERSION,
            "extracted_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_tickets": len(results),
            "source_mode": "ticket" if args.ticket else "inc+window" if args.inc else "file" if args.from_file else "jql",
            "threads_used": min(args.threads, len(tickets_to_extract)) if len(tickets_to_extract) > 1 else 1,
        },
        "tickets": results
    }
    
    # Determinar fichero de salida
    if args.output:
        output_file = args.output
    elif args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(args.output_dir, f"extraction_{timestamp}.json")
    else:
        # Default: nombre basado en el input
        if args.ticket:
            output_file = f"{args.ticket.upper()}_normalized.json"
        elif args.inc:
            output_file = f"{args.inc.upper()}_with_teccm.json"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"extraction_{timestamp}.json"
    
    # Escribir JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Extracción completada: {output_file}")
    print(f"  - Tickets extraídos: {len(results)}")
    
    # Resumen por tipo
    incidents = [t for t in results if t['ticket_type'] == 'INCIDENT']
    changes = [t for t in results if t['ticket_type'] == 'CHANGE']
    
    if incidents:
        print(f"  - Incidentes: {len(incidents)}")
    if changes:
        print(f"  - Cambios (TECCM): {len(changes)}")


if __name__ == "__main__":
    main()
