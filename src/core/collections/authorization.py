from src.core.auth.models import User

from .models import Collection, CollectionMember, MemberRole


def has_role(member: CollectionMember, *roles: MemberRole) -> bool:
    return member.role in set(roles)


def is_collection_owner(collection: Collection, user: User) -> bool:
    return collection.owner_id == user.id
