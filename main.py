from typing import Any

import json
from dataclasses import dataclass
from pathlib import Path

perms_file = Path("permissions.json")

perms_list = json.loads(perms_file.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Permission:
    resource: str
    action: str
    description: str | None = None

    @property
    def code(self) -> str:
        return f"{self.resource}:{self.action}"


permissions = [Permission(
            resource=perm["resource"],
            action=perm["action"],
            description=perm.get("description"),
        ) for perm in perms_list]


print(permissions)


@dataclass
class Identity:
    id: int
    permissions: set[str]

    def has_permission(self, perm: str) -> bool:
        return perm in self.permissions


identity = Identity(id=123, permissions={"task.create"})


def can_update_task(identity_: Identity) -> bool:
    return identity_.has_permission("task.update")


print(can_update_task(identity))
