"""Azure Table Storage backend for todo lists."""

import os
import uuid
from datetime import datetime
from typing import Optional
from azure.data.tables import TableServiceClient, TableClient
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from dotenv import load_dotenv

load_dotenv()

LISTS_TABLE = "todolists"
ITEMS_TABLE = "todoitems"


def get_connection_string() -> str:
    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        raise ValueError(
            "AZURE_STORAGE_CONNECTION_STRING environment variable not set.\n"
            "Set it or create a .env file with the connection string."
        )
    return conn_str


def ensure_tables(service: TableServiceClient) -> None:
    """Create tables if they don't exist."""
    for table_name in [LISTS_TABLE, ITEMS_TABLE]:
        try:
            service.create_table(table_name)
        except ResourceExistsError:
            pass


class TodoStorage:
    def __init__(self):
        conn_str = get_connection_string()
        self.service = TableServiceClient.from_connection_string(conn_str)
        ensure_tables(self.service)
        self.lists_table: TableClient = self.service.get_table_client(LISTS_TABLE)
        self.items_table: TableClient = self.service.get_table_client(ITEMS_TABLE)

    # ─── Lists ───────────────────────────────────────────────────────────────

    def get_lists(self) -> list[dict]:
        """Get all todo lists."""
        entities = self.lists_table.query_entities("PartitionKey eq 'lists'")
        return sorted(
            [{"id": e["RowKey"], "name": e["name"], "created_at": e.get("created_at", "")} for e in entities],
            key=lambda x: x.get("created_at", ""),
        )

    def create_list(self, name: str) -> dict:
        """Create a new todo list."""
        list_id = str(uuid.uuid4())[:8]
        entity = {
            "PartitionKey": "lists",
            "RowKey": list_id,
            "name": name,
            "created_at": datetime.utcnow().isoformat(),
        }
        self.lists_table.create_entity(entity)
        return {"id": list_id, "name": name}

    def update_list(self, list_id: str, name: str) -> None:
        """Update a list's name."""
        entity = self.lists_table.get_entity("lists", list_id)
        entity["name"] = name
        self.lists_table.update_entity(entity, mode="merge")

    def delete_list(self, list_id: str) -> None:
        """Delete a list and all its items."""
        # Delete all items in the list
        items = self.items_table.query_entities(f"PartitionKey eq '{list_id}'")
        for item in items:
            self.items_table.delete_entity(list_id, item["RowKey"])
        # Delete the list itself
        self.lists_table.delete_entity("lists", list_id)

    # ─── Items ───────────────────────────────────────────────────────────────

    def get_items(self, list_id: str) -> list[dict]:
        """Get all items in a list."""
        entities = self.items_table.query_entities(f"PartitionKey eq '{list_id}'")
        return sorted(
            [
                {
                    "id": e["RowKey"],
                    "title": e["title"],
                    "done": e.get("done", False),
                    "notes": e.get("notes", ""),
                    "created_at": e.get("created_at", ""),
                }
                for e in entities
            ],
            key=lambda x: (x.get("done", False), x.get("created_at", "")),
        )

    def create_item(self, list_id: str, title: str) -> dict:
        """Create a new todo item."""
        item_id = str(uuid.uuid4())[:8]
        entity = {
            "PartitionKey": list_id,
            "RowKey": item_id,
            "title": title,
            "done": False,
            "notes": "",
            "created_at": datetime.utcnow().isoformat(),
        }
        self.items_table.create_entity(entity)
        return {"id": item_id, "title": title, "done": False, "notes": ""}

    def update_item(self, list_id: str, item_id: str, title: Optional[str] = None, done: Optional[bool] = None, notes: Optional[str] = None) -> None:
        """Update a todo item."""
        entity = self.items_table.get_entity(list_id, item_id)
        if title is not None:
            entity["title"] = title
        if done is not None:
            entity["done"] = done
        if notes is not None:
            entity["notes"] = notes
        self.items_table.update_entity(entity, mode="merge")

    def delete_item(self, list_id: str, item_id: str) -> None:
        """Delete a todo item."""
        self.items_table.delete_entity(list_id, item_id)

    def clear_done(self, list_id: str) -> int:
        """Delete all completed items in a list. Returns count deleted."""
        items = self.items_table.query_entities(f"PartitionKey eq '{list_id}'")
        count = 0
        for item in items:
            if item.get("done"):
                self.items_table.delete_entity(list_id, item["RowKey"])
                count += 1
        return count

    def toggle_item(self, list_id: str, item_id: str) -> bool:
        """Toggle item done status. Returns new status."""
        entity = self.items_table.get_entity(list_id, item_id)
        new_done = not entity.get("done", False)
        entity["done"] = new_done
        self.items_table.update_entity(entity, mode="merge")
        return new_done
