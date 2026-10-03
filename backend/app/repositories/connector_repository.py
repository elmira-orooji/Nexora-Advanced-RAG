from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.connector import Connector
from app.models.document_set import DocumentSet


class ConnectorRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_set(self, set_id):
        return self.db.scalars(select(Connector).where(Connector.document_set_id == set_id)
                               .order_by(Connector.created_at.desc())).all()

    def get(self, connector_id):
        return self.db.get(Connector, connector_id)

    def set_exists(self, set_id, organization_id):
        return self.db.scalar(select(DocumentSet).where(
            DocumentSet.id == set_id, DocumentSet.organization_id == organization_id)) is not None

    def add(self, item):
        self.db.add(item)

    def flush(self):
        self.db.flush()

    def refresh(self, item):
        self.db.refresh(item)

    def delete(self, item):
        self.db.delete(item)
