#!/usr/bin/env python3
"""Small Google Keep command line client."""

from __future__ import annotations

import argparse
import datetime as _datetime
import getpass
import json
import os
import re
import secrets
import shutil
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

DEFAULT_KEYRING_SERVICE = "keep-cli"


class KeepCliError(Exception):
    """A user-facing CLI error."""


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except BrokenPipeError:
        return 1
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    except KeepCliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--email",
        default=argparse.SUPPRESS,
        help="Google account email. Defaults to KEEP_CLI_EMAIL or GOOGLE_EMAIL.",
    )
    common.add_argument(
        "--keyring-service",
        default=argparse.SUPPRESS,
        help=f"Keyring service name. Defaults to {DEFAULT_KEYRING_SERVICE}.",
    )

    json_parent = argparse.ArgumentParser(add_help=False)
    json_parent.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Print structured JSON output.",
    )

    mutation_parent = argparse.ArgumentParser(add_help=False)
    mutation_parent.add_argument(
        "--dry-run",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Validate and show the intended change without syncing it.",
    )
    mutation_parent.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Print structured JSON output.",
    )

    parser = argparse.ArgumentParser(
        prog="keep-cli",
        description="Read and safely update Google Keep notes with gkeepapi.",
        parents=[common],
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    auth = subparsers.add_parser("auth", help="Manage stored credentials")
    auth_subparsers = auth.add_subparsers(dest="auth_command", required=True)

    auth_status = auth_subparsers.add_parser(
        "status", parents=[common, json_parent], help="Show credential status"
    )
    auth_status.set_defaults(func=cmd_auth_status)

    set_token = auth_subparsers.add_parser(
        "set-token", parents=[common], help="Store a Google master token in keyring"
    )
    set_token.set_defaults(func=cmd_auth_set_token)

    exchange = auth_subparsers.add_parser(
        "exchange",
        parents=[common],
        help="Exchange a browser oauth_token for a master token",
    )
    exchange.add_argument("--oauth-token", required=True, help="Temporary oauth_token")
    exchange.add_argument(
        "--android-id",
        help="Android ID hex string. Defaults to a generated 16-character value.",
    )
    exchange.set_defaults(func=cmd_auth_exchange)

    logout = auth_subparsers.add_parser(
        "logout", parents=[common], help="Delete the stored keyring token"
    )
    logout.set_defaults(func=cmd_auth_logout)

    inbox = subparsers.add_parser(
        "inbox",
        aliases=["ls"],
        parents=[common, json_parent],
        help="List non-archived, non-trashed notes",
    )
    inbox.set_defaults(func=cmd_inbox)

    show = subparsers.add_parser(
        "show", parents=[common, json_parent], help="Show a note by ID or prefix"
    )
    show.add_argument("note", help="Full note ID or unambiguous ID prefix")
    show.set_defaults(func=cmd_show)

    find = subparsers.add_parser(
        "find", parents=[common, json_parent], help="Search note titles and text"
    )
    find.add_argument("query", help="Case-insensitive query")
    find.add_argument(
        "--inbox",
        action="store_true",
        help="Search only non-archived, non-trashed notes.",
    )
    find.add_argument(
        "--archived",
        action="store_true",
        help="Search only archived, non-trashed notes.",
    )
    find.add_argument(
        "--trashed",
        action="store_true",
        help="Search only trashed notes.",
    )
    find.add_argument(
        "--all",
        action="store_true",
        help="Search archived and trashed notes too.",
    )
    find.set_defaults(func=cmd_find)

    backup = subparsers.add_parser(
        "backup", parents=[common], help="Write a JSONL backup of Keep notes"
    )
    backup.add_argument(
        "--all",
        action="store_true",
        help="Include archived and trashed notes. Default is inbox only.",
    )
    backup.add_argument(
        "--output",
        "-o",
        help="Output JSONL path. Use '-' for stdout. Defaults to a timestamped file.",
    )
    backup.set_defaults(func=cmd_backup)

    edit = subparsers.add_parser(
        "edit",
        parents=[common, mutation_parent],
        help="Edit the title or text of a note",
    )
    edit.add_argument("note", help="Full note ID or unambiguous ID prefix")
    edit.add_argument("--title", help="Replacement title")
    text_group = edit.add_mutually_exclusive_group()
    text_group.add_argument("--text", help="Replacement text")
    text_group.add_argument("--text-file", type=Path, help="Read replacement text")
    text_group.add_argument(
        "--stdin", action="store_true", help="Read replacement text from stdin"
    )
    edit.set_defaults(func=cmd_edit)

    for name, func, help_text in [
        ("archive", cmd_archive, "Archive a note"),
        ("unarchive", cmd_unarchive, "Move a note out of the archive"),
        ("trash", cmd_trash, "Move a note to trash"),
        ("restore", cmd_restore, "Move a note out of trash"),
    ]:
        p = subparsers.add_parser(
            name, parents=[common, mutation_parent], help=help_text
        )
        p.add_argument("note", help="Full note ID or unambiguous ID prefix")
        p.set_defaults(func=func)

    delete = subparsers.add_parser(
        "delete",
        parents=[common, mutation_parent],
        help="Trash a note, or permanently delete it with --permanent --yes",
    )
    delete.add_argument("note", help="Full note ID or unambiguous ID prefix")
    delete.add_argument(
        "--permanent", action="store_true", help="Permanently delete the note"
    )
    delete.add_argument("--yes", action="store_true", help="Confirm permanent delete")
    delete.set_defaults(func=cmd_delete)

    items = subparsers.add_parser(
        "items",
        parents=[common, json_parent],
        help="List checklist items for a Keep list",
    )
    items.add_argument("note", help="Full note ID or unambiguous ID prefix")
    items.set_defaults(func=cmd_items)

    for name, func, help_text in [
        ("check", cmd_check, "Mark a checklist item checked"),
        ("uncheck", cmd_uncheck, "Mark a checklist item unchecked"),
        ("item-delete", cmd_item_delete, "Delete a checklist item"),
    ]:
        p = subparsers.add_parser(
            name, parents=[common, mutation_parent], help=help_text
        )
        p.add_argument("note", help="Full note ID or unambiguous ID prefix")
        p.add_argument("item", help="Full item ID or unambiguous ID prefix")
        p.set_defaults(func=func)

    item_edit = subparsers.add_parser(
        "item-edit",
        parents=[common, mutation_parent],
        help="Replace checklist item text",
    )
    item_edit.add_argument("note", help="Full note ID or unambiguous ID prefix")
    item_edit.add_argument("item", help="Full item ID or unambiguous ID prefix")
    item_edit.add_argument("--text", required=True, help="Replacement item text")
    item_edit.set_defaults(func=cmd_item_edit)

    return parser


def cmd_auth_status(args: argparse.Namespace) -> int:
    email = configured_email(args)
    service = keyring_service(args)
    result: dict[str, Any] = {
        "email": email,
        "keyring_service": service,
        "token_available": False,
        "token_source": None,
    }

    if not email:
        result["error"] = "missing email"
        if wants_json(args):
            emit_json(result)
        else:
            print("Email: missing")
            print("Set --email, KEEP_CLI_EMAIL, or GOOGLE_EMAIL.")
        return 1

    env_token, env_name = env_master_token()
    if env_token:
        result["token_available"] = True
        result["token_source"] = env_name
        if wants_json(args):
            emit_json(result)
        else:
            print(f"Email: {email}")
            print(f"Token: present via {env_name}")
        return 0

    try:
        token = get_keyring_token(email, service)
    except KeepCliError as exc:
        result["error"] = str(exc)
        if wants_json(args):
            emit_json(result)
        else:
            print(f"Email: {email}")
            print(f"Token: unavailable ({exc})")
            print(
                "Set KEEP_CLI_MASTER_TOKEN for one-off use if keyring is unavailable."
            )
        return 1

    result["token_available"] = bool(token)
    result["token_source"] = "keyring" if token else None
    if wants_json(args):
        emit_json(result)
    else:
        print(f"Email: {email}")
        if token:
            print(f"Token: present in keyring service '{service}'")
        else:
            print(f"Token: missing from keyring service '{service}'")
            print(f"Run: keep-cli auth set-token --email {email}")
    return 0 if token else 1


def cmd_auth_set_token(args: argparse.Namespace) -> int:
    email = require_email(args)
    service = keyring_service(args)
    token = read_secret_token()
    if not token:
        raise KeepCliError("No token was provided.")
    set_keyring_token(email, service, token)
    print(f"Stored token for {email} in keyring service '{service}'.")
    return 0


def cmd_auth_exchange(args: argparse.Namespace) -> int:
    email = require_email(args)
    service = keyring_service(args)
    android_id = args.android_id or secrets.token_hex(8)
    if not re.fullmatch(r"[0-9a-fA-F]+", android_id):
        raise KeepCliError("--android-id must be a hexadecimal string.")

    try:
        import gpsoauth  # type: ignore[import-not-found]
    except ImportError as exc:
        raise KeepCliError(
            "Missing dependency 'gpsoauth'. Run through `pybash ~/lib/keep_cli` "
            "or install lib/keep_cli/requirements.txt."
        ) from exc

    try:
        response = gpsoauth.exchange_token(email, args.oauth_token, android_id)
    except Exception as exc:  # pragma: no cover - depends on Google auth service.
        raise KeepCliError(f"Token exchange failed: {exc}") from exc

    master_token = response.get("Token")
    if not master_token:
        raise KeepCliError("Token exchange did not return a master token.")

    set_keyring_token(email, service, master_token)
    print(f"Stored exchanged token for {email} in keyring service '{service}'.")
    return 0


def cmd_auth_logout(args: argparse.Namespace) -> int:
    email = require_email(args)
    service = keyring_service(args)
    token = get_keyring_token(email, service)
    if not token:
        print(f"No stored token for {email} in keyring service '{service}'.")
        return 0
    delete_keyring_token(email, service)
    print(f"Deleted token for {email} from keyring service '{service}'.")
    return 0


def cmd_inbox(args: argparse.Namespace) -> int:
    keep = login_keep(args)
    notes = list(active_notes(keep.find(archived=False, trashed=False)))
    return emit_note_list(notes, args)


def cmd_show(args: argparse.Namespace) -> int:
    keep = login_keep(args)
    note = resolve_note(keep, args.note)
    if wants_json(args):
        emit_json(serialize_note(note))
    else:
        print_note_detail(note)
    return 0


def cmd_find(args: argparse.Namespace) -> int:
    archived, trashed = find_scope(args)
    keep = login_keep(args)
    needle = args.query.casefold()

    def matches(note: Any) -> bool:
        return (
            needle in note.title.casefold()
            or needle in note_search_text(note).casefold()
        )

    notes = list(
        active_notes(keep.find(func=matches, archived=archived, trashed=trashed))
    )
    return emit_note_list(notes, args)


def cmd_backup(args: argparse.Namespace) -> int:
    keep = login_keep(args)
    if args.all:
        notes = list(active_notes(keep.find(archived=None, trashed=None)))
    else:
        notes = list(active_notes(keep.find(archived=False, trashed=False)))

    lines = [json.dumps(serialize_note(note), sort_keys=True) for note in notes]
    if args.output == "-":
        for line in lines:
            print(line)
        return 0

    path = Path(args.output) if args.output else default_backup_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    except OSError as exc:
        raise KeepCliError(f"Could not write backup to {path}: {exc}") from exc

    print(f"Wrote {len(notes)} notes to {path}.")
    return 0


def cmd_edit(args: argparse.Namespace) -> int:
    text_value = read_edit_text(args)
    if args.title is None and text_value is None:
        raise KeepCliError(
            "Nothing to edit. Use --title, --text, --text-file, or --stdin."
        )

    def mutate(note: Any) -> None:
        if args.title is not None:
            note.title = args.title
        if text_value is not None:
            note.text = text_value

    def validate(note: Any) -> None:
        if text_value is not None and is_list_note(note):
            raise KeepCliError(
                "This is a checklist note. Use item-edit, check, uncheck, or "
                "item-delete instead of replacing text."
            )

    return mutate_note(args, "edit", mutate, validate)


def cmd_archive(args: argparse.Namespace) -> int:
    return mutate_note(args, "archive", lambda note: setattr(note, "archived", True))


def cmd_unarchive(args: argparse.Namespace) -> int:
    return mutate_note(args, "unarchive", lambda note: setattr(note, "archived", False))


def cmd_trash(args: argparse.Namespace) -> int:
    return mutate_note(args, "trash", lambda note: note.trash())


def cmd_restore(args: argparse.Namespace) -> int:
    return mutate_note(args, "restore", lambda note: note.untrash())


def cmd_delete(args: argparse.Namespace) -> int:
    if args.permanent and not args.yes:
        raise KeepCliError("Permanent deletion requires both --permanent and --yes.")
    if args.permanent:
        return mutate_note(args, "permanently delete", lambda note: note.delete())
    return mutate_note(args, "trash", lambda note: note.trash())


def cmd_items(args: argparse.Namespace) -> int:
    keep = login_keep(args)
    note = resolve_note(keep, args.note)
    require_list_note(note)
    items = list(note.items)
    if wants_json(args):
        emit_json(
            {
                "note": serialize_note_summary(note),
                "items": [serialize_item(item) for item in items],
            }
        )
    else:
        print_item_table(items)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    return mutate_item(args, "check", lambda item: setattr(item, "checked", True))


def cmd_uncheck(args: argparse.Namespace) -> int:
    return mutate_item(args, "uncheck", lambda item: setattr(item, "checked", False))


def cmd_item_edit(args: argparse.Namespace) -> int:
    return mutate_item(args, "edit item", lambda item: setattr(item, "text", args.text))


def cmd_item_delete(args: argparse.Namespace) -> int:
    return mutate_item(args, "delete item", lambda item: item.delete())


def mutate_note(
    args: argparse.Namespace,
    action: str,
    mutator: Callable[[Any], None],
    validator: Callable[[Any], None] | None = None,
) -> int:
    keep = login_keep(args)
    note = resolve_note(keep, args.note)
    if validator:
        validator(note)

    before = serialize_note(note)
    before_summary = describe_note(note)
    mutator(note)
    after = serialize_note(note)
    after_summary = describe_note(note)

    if is_dry_run(args):
        emit_note_change(
            action, before, after, before_summary, after_summary, True, args
        )
        return 0

    sync_keep(keep, action)
    emit_note_change(action, before, after, before_summary, after_summary, False, args)
    return 0


def mutate_item(
    args: argparse.Namespace,
    action: str,
    mutator: Callable[[Any], None],
) -> int:
    keep = login_keep(args)
    note = resolve_note(keep, args.note)
    require_list_note(note)
    item = resolve_item(note, args.item)

    before_item = serialize_item(item)
    before_label = describe_item(item)
    mutator(item)
    after_item = serialize_item(item)
    after_label = describe_item(item)

    if is_dry_run(args):
        emit_item_change(
            action, note, before_item, after_item, before_label, after_label, True, args
        )
        return 0

    sync_keep(keep, action)
    emit_item_change(
        action, note, before_item, after_item, before_label, after_label, False, args
    )
    return 0


def login_keep(args: argparse.Namespace) -> Any:
    email = require_email(args)
    token, _source = require_master_token(args, email)
    gkeepapi = import_gkeepapi()
    keep = gkeepapi.Keep()
    try:
        keep.authenticate(email, token)
    except Exception as exc:  # pragma: no cover - depends on Google auth service.
        raise KeepCliError(
            f"Could not authenticate Google Keep as {email}: {exc}"
        ) from exc
    return keep


def sync_keep(keep: Any, action: str) -> None:
    try:
        keep.sync()
    except Exception as exc:  # pragma: no cover - depends on Google Keep service.
        raise KeepCliError(
            f"Google Keep sync failed while trying to {action}: {exc}"
        ) from exc


def import_gkeepapi() -> Any:
    try:
        import gkeepapi  # type: ignore[import-not-found]
    except ImportError as exc:
        raise KeepCliError(
            "Missing dependency 'gkeepapi'. Run through `pybash ~/lib/keep_cli` "
            "or install lib/keep_cli/requirements.txt."
        ) from exc
    return gkeepapi


def configured_email(args: argparse.Namespace) -> str | None:
    return (
        getattr(args, "email", None)
        or os.environ.get("KEEP_CLI_EMAIL")
        or os.environ.get("GOOGLE_EMAIL")
    )


def require_email(args: argparse.Namespace) -> str:
    email = configured_email(args)
    if not email:
        raise KeepCliError(
            "No Google email configured. Pass --email, set KEEP_CLI_EMAIL, "
            "or set GOOGLE_EMAIL."
        )
    return email


def keyring_service(args: argparse.Namespace) -> str:
    return (
        getattr(args, "keyring_service", None)
        or os.environ.get("KEEP_CLI_KEYRING_SERVICE")
        or DEFAULT_KEYRING_SERVICE
    )


def env_master_token() -> tuple[str | None, str | None]:
    for name in ("KEEP_CLI_MASTER_TOKEN", "GOOGLE_MASTER_TOKEN"):
        value = os.environ.get(name)
        if value:
            return value, name
    return None, None


def require_master_token(args: argparse.Namespace, email: str) -> tuple[str, str]:
    env_token, env_name = env_master_token()
    if env_token:
        return env_token, env_name or "environment"

    service = keyring_service(args)
    token = get_keyring_token(email, service)
    if token:
        return token, f"keyring:{service}"

    raise KeepCliError(
        f"No Google master token found for {email}. Run "
        f"`keep-cli auth set-token --email {email}` or set KEEP_CLI_MASTER_TOKEN "
        "for this invocation."
    )


def import_keyring() -> Any:
    try:
        import keyring  # type: ignore[import-not-found]
    except ImportError as exc:
        raise KeepCliError(
            "Missing dependency 'keyring'. Run through `pybash ~/lib/keep_cli` "
            "or install lib/keep_cli/requirements.txt."
        ) from exc
    return keyring


def get_keyring_token(email: str, service: str) -> str | None:
    keyring = import_keyring()
    try:
        return keyring.get_password(service, email)
    except Exception as exc:  # pragma: no cover - backend-specific behavior.
        raise KeepCliError(
            f"Could not read keyring service '{service}': {exc}"
        ) from exc


def set_keyring_token(email: str, service: str, token: str) -> None:
    keyring = import_keyring()
    try:
        keyring.set_password(service, email, token)
    except Exception as exc:  # pragma: no cover - backend-specific behavior.
        raise KeepCliError(
            f"Could not write keyring service '{service}': {exc}"
        ) from exc


def delete_keyring_token(email: str, service: str) -> None:
    keyring = import_keyring()
    try:
        keyring.delete_password(service, email)
    except Exception as exc:  # pragma: no cover - backend-specific behavior.
        raise KeepCliError(
            f"Could not delete keyring token from '{service}': {exc}"
        ) from exc


def read_secret_token() -> str:
    if sys.stdin.isatty():
        return getpass.getpass("Google master token: ").strip()
    return sys.stdin.read().strip()


def read_edit_text(args: argparse.Namespace) -> str | None:
    if args.text is not None:
        return args.text
    if args.text_file is not None:
        try:
            return args.text_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise KeepCliError(
                f"Could not read text file {args.text_file}: {exc}"
            ) from exc
    if args.stdin:
        return sys.stdin.read()
    return None


def resolve_note(keep: Any, note_id_or_prefix: str) -> Any:
    target = note_id_or_prefix.casefold()
    notes = list(active_notes(keep.find(archived=None, trashed=None)))
    exact = [note for note in notes if note.id.casefold() == target]
    if exact:
        return exact[0]

    matches = [note for note in notes if note.id.casefold().startswith(target)]
    if not matches:
        raise KeepCliError(f"No note matches ID or prefix '{note_id_or_prefix}'.")
    if len(matches) > 1:
        preview = ", ".join(format_note_ref(note) for note in matches[:8])
        extra = "" if len(matches) <= 8 else f", and {len(matches) - 8} more"
        raise KeepCliError(
            f"Ambiguous note prefix '{note_id_or_prefix}' matches {preview}{extra}."
        )
    return matches[0]


def resolve_item(note: Any, item_id_or_prefix: str) -> Any:
    target = item_id_or_prefix.casefold()
    items = list(note.items)
    exact = [item for item in items if item.id.casefold() == target]
    if exact:
        return exact[0]

    matches = [item for item in items if item.id.casefold().startswith(target)]
    if not matches:
        raise KeepCliError(
            f"No checklist item matches ID or prefix '{item_id_or_prefix}'."
        )
    if len(matches) > 1:
        preview = ", ".join(format_item_ref(item) for item in matches[:8])
        extra = "" if len(matches) <= 8 else f", and {len(matches) - 8} more"
        raise KeepCliError(
            f"Ambiguous item prefix '{item_id_or_prefix}' matches {preview}{extra}."
        )
    return matches[0]


def active_notes(notes: Iterable[Any]) -> Iterable[Any]:
    return (note for note in notes if not getattr(note, "deleted", False))


def is_list_note(note: Any) -> bool:
    return note.__class__.__name__ == "List"


def require_list_note(note: Any) -> None:
    if not is_list_note(note):
        raise KeepCliError(
            f"Note {format_note_ref(note)} is not a checklist. Use `show` for text notes."
        )


def find_scope(args: argparse.Namespace) -> tuple[bool | None, bool | None]:
    chosen = [args.inbox, args.archived, args.trashed, args.all]
    if sum(bool(value) for value in chosen) > 1:
        raise KeepCliError(
            "Choose only one of --inbox, --archived, --trashed, or --all."
        )
    if args.all:
        return None, None
    if args.inbox:
        return False, False
    if args.archived:
        return True, False
    if args.trashed:
        return None, True
    return None, False


def emit_note_list(notes: list[Any], args: argparse.Namespace) -> int:
    if wants_json(args):
        emit_json([serialize_note(note) for note in notes])
    else:
        print_note_table(notes)
    return 0


def emit_note_change(
    action: str,
    before: dict[str, Any],
    after: dict[str, Any],
    before_summary: str,
    after_summary: str,
    dry_run: bool,
    args: argparse.Namespace,
) -> None:
    if wants_json(args):
        emit_json(
            {
                "action": action,
                "dry_run": dry_run,
                "before": before,
                "after": after,
            }
        )
        return

    verb = f"Would {action}" if dry_run else past_tense(action)
    print(f"{verb}: {after['id']}")
    print(f"  before: {before_summary}")
    print(f"  after:  {after_summary}")


def emit_item_change(
    action: str,
    note: Any,
    before: dict[str, Any],
    after: dict[str, Any],
    before_label: str,
    after_label: str,
    dry_run: bool,
    args: argparse.Namespace,
) -> None:
    if wants_json(args):
        emit_json(
            {
                "action": action,
                "dry_run": dry_run,
                "note": serialize_note_summary(note),
                "before": before,
                "after": after,
            }
        )
        return

    verb = f"Would {action}" if dry_run else past_tense(action)
    print(f"{verb}: {after['id']} in {format_note_ref(note)}")
    print(f"  before: {before_label}")
    print(f"  after:  {after_label}")


def past_tense(action: str) -> str:
    irregular = {
        "edit": "Edited",
        "edit item": "Edited item",
        "archive": "Archived",
        "unarchive": "Unarchived",
        "trash": "Trashed",
        "restore": "Restored",
        "check": "Checked",
        "uncheck": "Unchecked",
        "delete item": "Deleted item",
        "permanently delete": "Permanently deleted",
    }
    return irregular.get(action, action.capitalize())


def wants_json(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "json", False))


def is_dry_run(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "dry_run", False))


def emit_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def serialize_note(note: Any) -> dict[str, Any]:
    data = serialize_note_summary(note)
    data["timestamps"] = serialize_timestamps(note)
    if is_list_note(note):
        data["items"] = [serialize_item(item) for item in note.items]
        data["text"] = note_search_text(note)
    else:
        data["text"] = note.text
    return data


def serialize_note_summary(note: Any) -> dict[str, Any]:
    return {
        "id": note.id,
        "type": "list" if is_list_note(note) else "note",
        "title": note.title,
        "archived": bool(note.archived),
        "trashed": bool(note.trashed),
        "deleted": bool(getattr(note, "deleted", False)),
        "pinned": bool(note.pinned),
        "color": serialize_color(note.color),
        "url": getattr(note, "url", None),
    }


def serialize_timestamps(note: Any) -> dict[str, str | None]:
    timestamps = note.timestamps
    return {
        "created": datetime_to_str(getattr(timestamps, "created", None)),
        "updated": datetime_to_str(getattr(timestamps, "updated", None)),
        "edited": datetime_to_str(getattr(timestamps, "edited", None)),
        "trashed": datetime_to_str(getattr(timestamps, "trashed", None))
        if note.trashed
        else None,
        "deleted": datetime_to_str(getattr(timestamps, "deleted", None))
        if getattr(note, "deleted", False)
        else None,
    }


def serialize_item(item: Any) -> dict[str, Any]:
    return {
        "id": item.id,
        "text": item.text,
        "checked": bool(item.checked),
        "deleted": bool(getattr(item, "deleted", False)),
        "trashed": bool(getattr(item, "trashed", False)),
        "indented": bool(getattr(item, "indented", False)),
        "parent_item_id": getattr(getattr(item, "parent_item", None), "id", None),
    }


def serialize_color(color: Any) -> str:
    return getattr(color, "value", str(color))


def datetime_to_str(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def describe_note(note: Any) -> str:
    flags = []
    if note.pinned:
        flags.append("pinned")
    if note.archived:
        flags.append("archived")
    if note.trashed:
        flags.append("trashed")
    if getattr(note, "deleted", False):
        flags.append("deleted")
    state = ",".join(flags) if flags else "active"
    title = note.title or "(untitled)"
    if is_list_note(note):
        checked = sum(1 for item in note.items if item.checked)
        total = len(note.items)
        content = f"{checked}/{total} checked"
    else:
        content = f"{len(note.text)} chars"
    return f"{note_kind(note)} {state} title={title!r} {content}"


def describe_item(item: Any) -> str:
    marker = "[x]" if item.checked else "[ ]"
    deleted = " deleted" if getattr(item, "deleted", False) else ""
    indent = "  " if getattr(item, "indented", False) else ""
    return f"{indent}{marker}{deleted} {item.text}"


def note_kind(note: Any) -> str:
    return "list" if is_list_note(note) else "note"


def note_search_text(note: Any) -> str:
    if is_list_note(note):
        return "\n".join(item.text for item in note.items)
    return note.text


def note_preview(note: Any) -> str:
    if is_list_note(note):
        items = list(note.items)
        parts = [
            ("[x] " if item.checked else "[ ] ") + one_line(item.text)
            for item in items[:3]
        ]
        if len(items) > 3:
            parts.append(f"+{len(items) - 3} more")
        return "; ".join(parts)
    return one_line(note.text)


def print_note_table(notes: list[Any]) -> None:
    if not notes:
        print("No notes found.")
        return

    width = shutil.get_terminal_size((100, 24)).columns
    title_width = 30
    state_width = 18
    preview_width = max(24, width - 12 - 6 - state_width - title_width - 7)
    rows = [
        [
            "ID",
            "TYPE",
            "STATE",
            "TITLE",
            "PREVIEW",
        ]
    ]
    for note in notes:
        rows.append(
            [
                note.id[:12],
                note_kind(note),
                truncate(state_label(note), state_width),
                truncate(one_line(note.title or "(untitled)"), title_width),
                truncate(note_preview(note), preview_width),
            ]
        )
    print_table(rows)


def print_note_detail(note: Any) -> None:
    print(f"ID: {note.id}")
    print(f"Type: {note_kind(note)}")
    print(f"Title: {note.title or '(untitled)'}")
    print(f"State: {state_label(note)}")
    print(f"Updated: {datetime_to_str(note.timestamps.updated)}")
    print(f"URL: {getattr(note, 'url', '')}")
    if is_list_note(note):
        print()
        print("Items:")
        if not note.items:
            print("  No checklist items.")
        for item in note.items:
            indent = "  " if getattr(item, "indented", False) else ""
            marker = "[x]" if item.checked else "[ ]"
            print(f"  {indent}{item.id[:12]} {marker} {item.text}")
    else:
        print()
        print("Text:")
        print(note.text)


def print_item_table(items: list[Any]) -> None:
    if not items:
        print("No checklist items found.")
        return
    rows = [["ID", "DONE", "TEXT"]]
    for item in items:
        indent = "  " if getattr(item, "indented", False) else ""
        rows.append([item.id[:12], "yes" if item.checked else "no", indent + item.text])
    print_table(rows)


def print_table(rows: list[list[str]]) -> None:
    widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]))]
    for row_index, row in enumerate(rows):
        line = "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        print(line.rstrip())
        if row_index == 0:
            print("  ".join("-" * width for width in widths).rstrip())


def state_label(note: Any) -> str:
    flags = []
    if note.pinned:
        flags.append("pinned")
    if note.archived:
        flags.append("archived")
    if note.trashed:
        flags.append("trashed")
    if getattr(note, "deleted", False):
        flags.append("deleted")
    return ",".join(flags) if flags else "active"


def one_line(value: str) -> str:
    return " ".join(value.split())


def truncate(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    if width <= 1:
        return value[:width]
    return value[: width - 1] + "~"


def format_note_ref(note: Any) -> str:
    return f"{note.id[:12]}:{one_line(note.title or '(untitled)')}"


def format_item_ref(item: Any) -> str:
    return f"{item.id[:12]}:{one_line(item.text)}"


def default_backup_path() -> Path:
    now = _datetime.datetime.now(tz=_datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    return Path.cwd() / f"keep-backup-{now}.jsonl"


if __name__ == "__main__":
    raise SystemExit(main())
