"""Flatten the CFBD OpenAPI spec into tabular rows.

CFBD publishes the v2 spec at https://apinext.collegefootballdata.com/api-docs.json. It is
complete on structure — every entity, field, type, format, nullability and enum — and almost
silent on meaning: four of 1,017 response fields carry a description. So this module answers
"what fields exist"; `definitions.py` answers "what they mean".

Fields are flattened to dot-paths, with `[]` marking an array of objects. A shared child
entity (Venue under both Team and Game, say) is repeated under each parent rather than
referenced, because the dictionary's reader wants one row per thing they will actually see in
a flattened table.
"""
from typing import Dict, List, Optional, Tuple

MAX_DEREF = 20


class Spec:
    """A loaded OpenAPI document."""

    def __init__(self, doc: dict):
        self.doc = doc
        self.schemas: Dict[str, dict] = doc.get("components", {}).get("schemas", {})

    @property
    def version(self) -> str:
        return self.doc.get("info", {}).get("version", "unknown")

    # ---------------------------------------------------------------- schema walking
    def deref(self, node) -> Tuple[dict, Optional[str]]:
        """Resolve $ref / allOf down to a concrete schema, returning (schema, ref_name)."""
        name = None
        for _ in range(MAX_DEREF):
            if not isinstance(node, dict):
                break
            if "$ref" in node:
                name = node["$ref"].split("/")[-1]
                node = self.schemas.get(name, {})
                continue
            if "allOf" in node:
                merged = {k: v for k, v in node.items() if k != "allOf"}
                for part in node["allOf"]:
                    sub, sub_name = self.deref(part)
                    if sub_name and name is None:
                        name = sub_name
                    for key, value in sub.items():
                        if key == "properties":
                            merged.setdefault("properties", {}).update(value)
                        else:
                            merged.setdefault(key, value)
                node = merged
                continue
            break
        return (node if isinstance(node, dict) else {}), name

    def type_label(self, node: dict, ref_name: Optional[str]) -> str:
        if node.get("enum"):
            return "enum<{}>".format(ref_name or "inline")
        node_type, fmt = node.get("type"), node.get("format")
        if node_type == "array":
            items, item_name = self.deref(node.get("items") or {})
            if items.get("properties") or items.get("type") == "object" or item_name:
                return "array<{}>".format(item_name or "object")
            inner_fmt = items.get("format")
            return "array<{}{}>".format(items.get("type") or "any", "/" + inner_fmt if inner_fmt else "")
        if node_type == "object" or node.get("properties"):
            return "object<{}>".format(ref_name) if ref_name else "object"
        if node_type is None and ref_name:
            return ref_name
        return "{}{}".format(node_type or "any", "/" + fmt if fmt else "")

    @staticmethod
    def enum_values(node: dict) -> str:
        return "; ".join(str(v) for v in node["enum"]) if node.get("enum") else ""

    def flatten(self, node, prefix: str = "", stack: Optional[List[str]] = None,
                depth: int = 0) -> List[dict]:
        """One row per leaf field, keyed by dot-path.

        `stack` holds the ANCESTOR entity names on the current path. An entity is pushed only
        once the guard below has cleared it — pushing before the check made every
        array-of-entity look self-recursive, which silently truncated eight endpoints the
        first time this ran.
        """
        stack = stack or []
        rows: List[dict] = []
        node, ref_name = self.deref(node)

        if node.get("type") == "array":
            items, _ = self.deref(node.get("items") or {})
            if items.get("properties"):
                return self.flatten(node.get("items"), prefix + "[]", stack, depth + 1)

        props = node.get("properties")
        if props:
            if ref_name and ref_name in stack and depth > 0:
                return [dict(path=prefix, type="object<{}>".format(ref_name), enum="",
                             nullable="", required="",
                             description="RECURSIVE -> {}; not expanded".format(ref_name))]
            required = set(node.get("required") or [])
            child_stack = stack + ([ref_name] if ref_name else [])
            for name, prop in props.items():
                path = "{}.{}".format(prefix, name) if prefix else name
                child, child_ref = self.deref(prop)
                child_items, _ = self.deref(child.get("items") or {})
                is_container = bool(child.get("properties")) or (
                    child.get("type") == "array" and bool(child_items.get("properties")))
                if is_container:
                    rows.extend(self.flatten(prop, path, child_stack, depth + 1))
                else:
                    rows.append(dict(
                        path=path,
                        type=self.type_label(child, child_ref),
                        enum=self.enum_values(child),
                        nullable="yes" if (prop.get("nullable") or child.get("nullable")) else "no",
                        required="yes" if name in required else "no",
                        description=prop.get("description") or child.get("description") or "",
                    ))
            return rows

        return [dict(path=prefix or "(scalar)", type=self.type_label(node, ref_name),
                     enum=self.enum_values(node),
                     nullable="yes" if node.get("nullable") else "no",
                     required="", description=node.get("description") or "")]

    # ---------------------------------------------------------------- extraction
    def response_entity(self, operation: dict) -> Tuple[Optional[dict], Optional[str], bool]:
        try:
            schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
        except (KeyError, TypeError):
            return None, None, False
        is_array = schema.get("type") == "array"
        target = schema.get("items") if is_array else schema
        _, name = self.deref(target)
        return target, name, is_array

    def extract(self, keys=None) -> Tuple[List[dict], List[dict], List[dict]]:
        """Return (endpoints, fields, parameters) rows.

        `keys` optionally restricts output to these raw-directory keys — the same
        `path.replace("/", "_")` convention `src.endpoints.Endpoint.key` uses.
        """
        endpoints, fields, parameters = [], [], []
        for path, operations in self.doc.get("paths", {}).items():
            key = path.strip("/").replace("/", "_")
            if keys is not None and key not in keys:
                continue
            for operation in operations.values():
                target, entity, is_array = self.response_entity(operation)
                endpoints.append(dict(
                    endpoint=path, key=key,
                    operation_id=operation.get("operationId", ""),
                    tag=(operation.get("tags") or [""])[0],
                    description=operation.get("description", ""),
                    entity=entity or "",
                    returns_array="yes" if is_array else "no",
                ))
                for param in operation.get("parameters") or []:
                    node, ref = self.deref(param.get("schema") or {})
                    parameters.append(dict(
                        endpoint=path, key=key, parameter=param.get("name", ""),
                        location=param.get("in", ""),
                        required="yes" if param.get("required") else "no",
                        type=self.type_label(node, ref), enum=self.enum_values(node),
                        description=param.get("description", ""),
                    ))
                if target is not None:
                    for row in self.flatten(target):
                        fields.append(dict(
                            endpoint=path, key=key, entity=entity or "",
                            field_path=row["path"], type=row["type"],
                            enum_values=row["enum"], nullable=row["nullable"],
                            required=row["required"], description=row["description"],
                        ))
        return endpoints, fields, parameters

    def vocabularies(self) -> List[dict]:
        """The spec's controlled vocabularies — bare string schemas carrying an enum."""
        out = []
        for name, schema in self.schemas.items():
            if schema.get("type") == "string" and schema.get("enum"):
                out.append(dict(name=name, values=schema["enum"]))
        return sorted(out, key=lambda v: v["name"])
