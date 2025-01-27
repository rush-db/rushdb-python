from typing import List

from src.rushdb import RushDBClient


class LabelsAPI:
    """API for managing labels in RushDB."""
    def __init__(self, client: 'RushDBClient'):
        self.client = client

    def list(self) -> List[str]:
        """List all labels."""
        return self.client._make_request('GET', '/api/v1/labels')

    def create(self, label: str) -> None:
        """Create a new label."""
        return self.client._make_request('POST', '/api/v1/labels', {'name': label})

    def delete(self, label: str) -> None:
        """Delete a label."""
        return self.client._make_request('DELETE', f'/api/v1/labels/{label}')
