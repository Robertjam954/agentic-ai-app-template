import asyncio
import json

from sqlmodel import Session

from app.agents.tools import ToolContext, run_tool
from app.models import Item
from tests.utils.user import create_random_user


def test_search_items_returns_only_accessible_items(db: Session) -> None:
    user = create_random_user(db)
    other_user = create_random_user(db)
    owned_item = Item(title="Tool-owned item", owner_id=user.id)
    other_item = Item(title="Tool-other item", owner_id=other_user.id)
    db.add(owned_item)
    db.add(other_item)
    db.commit()

    result = asyncio.run(
        run_tool(
            "search_items",
            {"query": "Tool"},
            ToolContext(session=db, user=user),
        )
    )

    assert owned_item.created_at is not None
    assert json.loads(result) == [
        {
            "id": str(owned_item.id),
            "title": "Tool-owned item",
            "description": None,
            "created_at": owned_item.created_at.isoformat(),
        }
    ]
