"""
Jira client wrapper.
Maneja la conexión a Jira con las credenciales proporcionadas.
"""

import logging
from typing import Optional, Tuple
from jira import JIRA
from jira.exceptions import JIRAError

from ..config import get_settings

logger = logging.getLogger(__name__)


class JiraClient:
    """Cliente de Jira con gestión de conexión."""

    def __init__(self, username: str, password: str, url: Optional[str] = None):
        self.username = username
        self.password = password
        self.url = url or get_settings().jira_url
        self._client: Optional[JIRA] = None

    def connect(self) -> Tuple[bool, str]:
        """
        Conecta a Jira.
        Returns: (success, message)
        """
        try:
            self._client = JIRA(
                server=self.url,
                basic_auth=(self.username, self.password)
            )
            # Test connection by getting current user
            myself = self._client.myself()
            logger.info(f"Connected to Jira as {myself['displayName']}")
            return True, f"Conectado como {myself['displayName']}"
        except JIRAError as e:
            logger.error(f"Jira connection error: {e.status_code} - {e.text}")
            if e.status_code == 401:
                return False, "Credenciales inválidas"
            elif e.status_code == 403:
                return False, "Acceso denegado"
            else:
                return False, f"Error de conexión: {e.text}"
        except Exception as e:
            logger.exception(f"Unexpected error connecting to Jira: {e}")
            return False, f"Error inesperado: {str(e)}"

    @property
    def client(self) -> JIRA:
        """Get the JIRA client instance."""
        if self._client is None:
            raise RuntimeError("Not connected to Jira. Call connect() first.")
        return self._client

    def test_connection(self) -> bool:
        """Test if connection is still valid."""
        try:
            self._client.myself()
            return True
        except:
            return False


def create_jira_client(username: str, password: str) -> JiraClient:
    """Factory function to create a JiraClient."""
    return JiraClient(username, password)
