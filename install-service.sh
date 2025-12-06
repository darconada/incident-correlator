#!/bin/bash
# Script para instalar el servicio systemd de INC-TECCM Analyzer
# Ejecutar con: sudo bash install-service.sh

set -e

SERVICE_NAME="inc-teccm-analyzer"
SERVICE_FILE="$(dirname "$0")/${SERVICE_NAME}.service"
SYSTEMD_DIR="/etc/systemd/system"

echo "=== Instalando servicio ${SERVICE_NAME} ==="

# Verificar que el archivo de servicio existe
if [ ! -f "$SERVICE_FILE" ]; then
    echo "Error: No se encuentra el archivo ${SERVICE_FILE}"
    exit 1
fi

# Copiar archivo de servicio
echo "Copiando archivo de servicio..."
cp "$SERVICE_FILE" "${SYSTEMD_DIR}/${SERVICE_NAME}.service"

# Recargar systemd
echo "Recargando systemd..."
systemctl daemon-reload

# Habilitar el servicio para que arranque en boot
echo "Habilitando servicio para arranque automatico..."
systemctl enable "$SERVICE_NAME"

# Iniciar el servicio
echo "Iniciando servicio..."
systemctl start "$SERVICE_NAME"

# Mostrar estado
echo ""
echo "=== Estado del servicio ==="
systemctl status "$SERVICE_NAME" --no-pager

echo ""
echo "=== Instalacion completada ==="
echo "Comandos utiles:"
echo "  Ver estado:    sudo systemctl status ${SERVICE_NAME}"
echo "  Ver logs:      sudo journalctl -u ${SERVICE_NAME} -f"
echo "  Reiniciar:     sudo systemctl restart ${SERVICE_NAME}"
echo "  Parar:         sudo systemctl stop ${SERVICE_NAME}"
echo ""
echo "La aplicacion estara disponible en: http://localhost:5178"
