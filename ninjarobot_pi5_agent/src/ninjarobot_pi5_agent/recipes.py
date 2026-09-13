"""User-owned, versioned linear read-only recipes; saved data is never permission."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from jsonschema import Draft202012Validator
from pydantic import Field, StringConstraints, model_validator

from ninjarobot_pi5_ide import RiskLevel

from .models import AgentContractModel, ToolDefinition, ToolName

# Deliberately closed: deferred calendar/research/notes and hardware cannot enter recipes.
READ_TOOLS = frozenset(
    {
        "system.time.get",
        "command_help.search",
        "project_help.search",
        "project_help.read",
        "tasks.list",
        "memory.search",
        "memory.profile.get",
    }
)


class RecipeStep(AgentContractModel):
    tool: ToolName
    arguments: dict[str, Any] = Field(default_factory=dict)
    expected: Annotated[str, StringConstraints(min_length=1, max_length=300)]
    result_fields: tuple[
        Annotated[str, StringConstraints(pattern=r"^[a-zA-Z][a-zA-Z0-9_]{0,63}$")], ...
    ] = ()


class Recipe(AgentContractModel):
    schema_version: Literal[1] = 1
    id: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]{0,62}$")]
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    purpose: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    inputs: dict[str, Literal["string", "integer", "boolean"]] = Field(default_factory=dict)
    steps: Annotated[tuple[RecipeStep, ...], Field(min_length=1, max_length=8)]
    max_seconds: Annotated[int, Field(ge=1, le=60)] = 30
    source_task_ids: Annotated[tuple[str, ...], Field(max_length=8)] = ()

    @model_validator(mode="after")
    def bounded(self) -> Recipe:
        if len(self.model_dump_json().encode()) > 16000 or len(self.inputs) > 12:
            raise ValueError("recipe exceeds its size/input budget")
        for index, step in enumerate(self.steps):
            if step.tool not in READ_TOOLS:
                raise ValueError("recipes permit only the reviewed local read-only tool list")
            for value in step.arguments.values():
                if isinstance(value, dict) and "$input" in value:
                    if (
                        set(value) != {"$input"}
                        or not isinstance(value["$input"], str)
                        or value["$input"] not in self.inputs
                    ):
                        raise ValueError("unknown input reference")
                elif isinstance(value, dict) and "$result" in value:
                    reference = value["$result"]
                    if (
                        set(value) != {"$result"}
                        or not isinstance(reference, list)
                        or len(reference) != 2
                    ):
                        raise ValueError(
                            "result reference must be [earlier step index, declared field]"
                        )
                    prior, field = reference
                    if (
                        type(prior) is not int
                        or not 0 <= prior < index
                        or field not in self.steps[prior].result_fields
                    ):
                        raise ValueError("future, cyclic or undeclared result reference")
                elif isinstance(value, (dict, list)):
                    raise ValueError("arguments are scalar values or explicit top-level references")
        return self


def contract_hash(tool: ToolDefinition) -> str:
    return hashlib.sha256(tool.model_dump_json().encode()).hexdigest()


def review(recipe: Recipe, definitions: tuple[ToolDefinition, ...]) -> dict[str, Any]:
    catalog = {item.name: item for item in definitions}
    contracts = {}
    for step in recipe.steps:
        tool = catalog.get(step.tool)
        if tool is None or tool.risk is not RiskLevel.READ_ONLY or not tool.idempotent:
            raise ValueError(f"required read-only capability unavailable: {step.tool}")
        contracts[step.tool] = contract_hash(tool)
        # Validate all concrete values now; referenced values are validated again at execution.
        concrete = {
            key: value for key, value in step.arguments.items() if not isinstance(value, dict)
        }
        schema = dict(tool.input_schema)
        schema["required"] = [
            key
            for key in schema.get("required", [])
            if key not in step.arguments or key in concrete
        ]
        Draft202012Validator(schema).validate(concrete)
        if any(key not in tool.input_schema.get("properties", {}) for key in step.arguments):
            raise ValueError("unknown tool argument")
    data = {"recipe": recipe.model_dump(mode="json"), "contracts": contracts}
    digest = hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        **data,
        "review_hash": digest,
        "effects": "local read-only tools; private saved recipe and request receipts",
        "simulation_only": True,
        "executed": False,
        "warning": "Preview validates contracts; it does not prove expected results. "
        "Saving does not run.",
    }


def resolve_arguments(
    recipe: Recipe, step: RecipeStep, inputs: dict[str, Any], results: list[dict[str, Any]]
) -> dict[str, Any]:
    if set(inputs) != set(recipe.inputs):
        raise ValueError("provide exactly the declared recipe inputs")
    types = {"string": str, "integer": int, "boolean": bool}
    if any(type(inputs[key]) is not types[kind] for key, kind in recipe.inputs.items()):
        raise ValueError("recipe input type mismatch")
    arguments = {}
    for key, value in step.arguments.items():
        if isinstance(value, dict):
            if "$input" in value:
                value = inputs[value["$input"]]
            else:
                index, field = value["$result"]
                value = results[index][field]
            if not isinstance(value, (str, int, float, bool)) and value is not None:
                raise ValueError("only scalar result references are supported")
        arguments[key] = value
    if len(json.dumps(arguments).encode()) > 16000:
        raise ValueError("resolved arguments exceed budget")
    return arguments


class RecipeStore:
    """Small transactions in the existing migrated Agent database; no background worker."""

    def __init__(self, path: Path) -> None:
        self.path = path

    async def action(
        self,
        scope: str,
        user_id: str | None,
        operation: str,
        *,
        recipe_id: str = "",
        version: int = 0,
        preview: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._action, scope, user_id, operation, recipe_id, version, preview
        )

    def _action(
        self,
        scope: str,
        user_id: str | None,
        operation: str,
        recipe_id: str,
        version: int,
        preview: dict[str, Any] | None,
    ) -> dict[str, Any]:
        connection = sqlite3.connect(self.path.resolve().as_uri() + "?mode=rw", uri=True, timeout=5)
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                if operation == "list":
                    rows = connection.execute(
                        "SELECT recipe_id, version, enabled FROM task_recipes WHERE "
                        "owner_scope=? ORDER BY recipe_id LIMIT 100",
                        (scope,),
                    ).fetchall()
                    return {
                        "recipes": [
                            {"id": r[0], "version": r[1], "enabled": bool(r[2])} for r in rows
                        ]
                    }
                if operation == "save":
                    assert preview is not None
                    recipe_id = preview["recipe"]["id"]
                    row = connection.execute(
                        "SELECT version FROM task_recipes WHERE owner_scope=? AND recipe_id=?",
                        (scope, recipe_id),
                    ).fetchone()
                    count = connection.execute(
                        "SELECT COUNT(*) FROM task_recipes WHERE owner_scope=?", (scope,)
                    ).fetchone()[0]
                    if row is None and count >= 100:
                        raise ValueError(
                            "owned recipe limit reached (100); delete an unwanted recipe"
                        )
                    current = row[0] if row else 0
                    if version != current:
                        raise ValueError("recipe was changed concurrently; preview and save again")
                    next_version = connection.execute(
                        "SELECT COALESCE(MAX(version), 0)+1 FROM task_recipe_versions "
                        "WHERE owner_scope=? AND recipe_id=?",
                        (scope, recipe_id),
                    ).fetchone()[0]
                    if next_version > 100:
                        raise ValueError("recipe version limit reached (100); use a new recipe ID")
                    stored = {
                        **preview,
                        "saved_id": uuid.uuid4().hex,
                        "saved_at": datetime.now(UTC).isoformat(),
                    }
                    connection.execute(
                        "INSERT INTO task_recipes(owner_scope, user_id, recipe_id, "
                        "version, enabled) VALUES (?,?,?,?,1) ON "
                        "CONFLICT(owner_scope,recipe_id) DO UPDATE SET version=excluded.version",
                        (scope, user_id, recipe_id, next_version),
                    )
                    connection.execute(
                        "INSERT INTO task_recipe_versions VALUES (?,?,?,?)",
                        (scope, recipe_id, next_version, json.dumps(stored)),
                    )
                    return {"id": recipe_id, "version": next_version, "executed": False}
                row = connection.execute(
                    "SELECT version,enabled FROM task_recipes WHERE owner_scope=? AND recipe_id=?",
                    (scope, recipe_id),
                ).fetchone()
                if row is None:
                    raise KeyError("unknown owned recipe")
                if operation in {"disable", "enable"}:
                    connection.execute(
                        "UPDATE task_recipes SET enabled=? WHERE owner_scope=? AND recipe_id=?",
                        (operation == "enable", scope, recipe_id),
                    )
                    return {"id": recipe_id, "enabled": operation == "enable"}
                if operation == "delete":
                    connection.execute(
                        "DELETE FROM task_recipes WHERE owner_scope=? AND recipe_id=?",
                        (scope, recipe_id),
                    )
                    return {"id": recipe_id, "deleted": True}
                selected = version or row[0]
                saved = connection.execute(
                    "SELECT record_json FROM task_recipe_versions WHERE owner_scope=? "
                    "AND recipe_id=? AND version=?",
                    (scope, recipe_id, selected),
                ).fetchone()
                if saved is None:
                    raise KeyError("unknown recipe version")
                if operation == "rollback":
                    connection.execute(
                        "UPDATE task_recipes SET version=? WHERE owner_scope=? AND recipe_id=?",
                        (selected, scope, recipe_id),
                    )
                elif operation != "show":
                    raise ValueError("unknown recipe operation")
                return {**json.loads(saved[0]), "version": selected, "enabled": bool(row[1])}
        finally:
            connection.close()
