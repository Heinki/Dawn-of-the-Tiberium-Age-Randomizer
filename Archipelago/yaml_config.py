"""Small dependency-free reader/writer for Dawn of the Tiberium Age player YAML files."""

from __future__ import annotations

import json

from randomizer.config.player import (
    parse_simple_yaml_text,
    simple_yaml_mapping_lines,
)


GAME_NAME = "Dawn of the Tiberium Age"


def _quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def serialize_player_yaml(settings, slot_name):
    """Export reusable gameplay settings, never generated run data.

    Accept an old manifest argument for callers upgrading from earlier releases;
    only its player settings are exported.
    """
    from Archipelago.run_manifest import gameplay_config_snapshot

    if not isinstance(settings, dict):
        raise ValueError("Launcher settings must be a mapping.")
    if "frozen_settings" in settings:
        settings = settings["frozen_settings"].get("launcher", {})
    launcher_settings = gameplay_config_snapshot(settings)
    launcher_settings.pop("seed", None)
    if not isinstance(launcher_settings, dict) or not launcher_settings:
        raise ValueError("Player YAML needs readable launcher settings.")
    output = (
        f"name: {_quote(str(slot_name).strip() or 'Commander')}\n"
        f"game: {GAME_NAME}\n"
        "description: Dawn of the Tiberium Age Randomizer player settings\n"
        "requires:\n"
        "  version: 0.6.7\n\n"
        f"{GAME_NAME}:\n"
        "  # Reuse this file for every new Archipelago seed.\n"
        "  # Archipelago generates missions, Grid, starters and rewards.\n"
        "  launcher_settings:\n"
    )
    return output + "\n".join(simple_yaml_mapping_lines(launcher_settings, 4)) + "\n"


def _scalar(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return json.loads(value)
    return value


def parse_player_yaml(text):
    """Read only the fields this launcher owns, rejecting ambiguous files."""
    lines = str(text).lstrip("\ufeff").splitlines()
    top = {}
    manifest_parts = []
    launcher_setting_lines = []
    in_game = False
    capture_manifest = False
    capture_launcher_settings = False
    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent == 0:
            capture_manifest = False
            capture_launcher_settings = False
            in_game = stripped == f"{GAME_NAME}:"
            if ":" in stripped and not stripped.endswith(":"):
                key, value = stripped.split(":", 1)
                top[key.strip()] = _scalar(value)
            continue
        if in_game and indent == 2:
            capture_manifest = False
            capture_launcher_settings = False
            if stripped.startswith("launcher_settings:"):
                capture_launcher_settings = True
                inline = stripped.split(":", 1)[1].strip()
                if inline:
                    launcher_setting_lines.append(inline)
                continue
            if stripped.startswith(("generated_world:", "run_manifest:")):
                capture_manifest = True
                inline = stripped.split(":", 1)[1].strip()
                if inline and inline not in {">", ">-", "|", "|-"}:
                    manifest_parts.append(_scalar(inline))
                continue
        if capture_launcher_settings:
            if indent < 4:
                capture_launcher_settings = False
            else:
                launcher_setting_lines.append(raw[4:])
                continue
        if capture_manifest:
            if indent < 4:
                capture_manifest = False
            else:
                manifest_parts.append(raw[4:].strip())
    if top.get("game") != GAME_NAME:
        raise ValueError("Player YAML game must be Dawn of the Tiberium Age.")
    slot_name = str(top.get("name") or "").strip()
    if not slot_name:
        raise ValueError("Player YAML has no slot name.")
    manifest = None
    if manifest_parts:
        try:
            manifest = json.loads(" ".join(manifest_parts))
        except json.JSONDecodeError as exc:
            raise ValueError("Player YAML legacy manifest is not valid JSON.") from exc
        if not isinstance(manifest, dict):
            raise ValueError("Player YAML legacy manifest must be an object.")
    settings_text = "\n".join(launcher_setting_lines).strip()
    launcher_settings = (
        json.loads(settings_text) if settings_text.startswith("{")
        else parse_simple_yaml_text(settings_text)
    ) if settings_text else {}
    if not launcher_settings and manifest is not None:
        frozen = manifest.get("frozen_settings")
        launcher_settings = (
            frozen.get("launcher") if isinstance(frozen, dict) else None
        )
    if not isinstance(launcher_settings, dict) or not launcher_settings:
        raise ValueError(
            "Player YAML has no readable or manifest-frozen launcher_settings."
        )
    return {
        "name": slot_name,
        "game": GAME_NAME,
        "launcher_settings": launcher_settings,
        "run_manifest": manifest,
    }
