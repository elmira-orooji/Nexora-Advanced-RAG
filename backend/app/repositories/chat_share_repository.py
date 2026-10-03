from sqlalchemy import select

from app.models.chat_share import ChatShare
from app.models.user import User


class ChatShareRepository:
    def __init__(self, db):
        self.db = db

    def resolve(self, token_hash):
        return self.db.scalar(select(ChatShare).where(ChatShare.token_hash == token_hash, ChatShare.is_active.is_(True)))

    def owner(self, owner_id):
        return self.db.get(User, owner_id)

    def get(self, share_id):
        return self.db.get(ChatShare, share_id)

    def list_active(self, user_id):
        return self.db.scalars(select(ChatShare).where(ChatShare.owner_id == user_id, ChatShare.is_active.is_(True)).order_by(ChatShare.created_at.desc())).all()

    def add(self, item):
        self.db.add(item)

    def refresh(self, item):
        self.db.refresh(item)
