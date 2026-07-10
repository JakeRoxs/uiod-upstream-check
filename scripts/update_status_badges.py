import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX = ROOT / "badges" / "index.json"
DEFAULT_UIOD_WORKSHOP_ID = "1623423360"


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def resolve_repo_path(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def badge_url(label: str, message: str, color: str) -> str:
    encoded_label = quote(label.replace("-", "--"), safe="")
    encoded_message = quote(message.replace("-", "--"), safe="")
    encoded_color = quote(color, safe="")
    return f"https://img.shields.io/badge/{encoded_label}-{encoded_message}-{encoded_color}"


def timestamp_version(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, UTC).strftime("%Y.%m.%d.%H%M")


def current_timestamp_version() -> str:
    return datetime.now(UTC).strftime("%Y.%m.%d.%H%M")


def parse_keyvalues_object(text: str) -> dict:
    tokens = re_keyvalues_tokens(text)
    parsed, next_index = parse_keyvalues_tokens(tokens, 0)
    if next_index != len(tokens):
        raise ValueError("Unexpected trailing KeyValues tokens.")
    return parsed


def parse_keyvalues_tokens(tokens: list[str], index: int) -> tuple[dict, int]:
    result = {}
    while index < len(tokens):
        token = tokens[index]
        if token == "}":
            return result, index + 1
        key = keyvalues_key(token)
        value, index = parse_keyvalues_value(tokens, index + 1, key)
        result[key] = value
    return result, index


def keyvalues_key(token: str) -> str:
    if token == "{":
        raise ValueError("Unexpected object start in KeyValues input.")
    return token


def parse_keyvalues_value(tokens: list[str], index: int, key: str) -> tuple[object, int]:
    if index >= len(tokens):
        raise ValueError(f"Missing value for KeyValues key: {key}")
    if tokens[index] == "{":
        return parse_keyvalues_tokens(tokens, index + 1)
    return tokens[index], index + 1


def re_keyvalues_tokens(text: str) -> list[str]:
    import re

    tokens = []
    for match in re.finditer(r'"((?:\\.|[^"\\])*)"|([{}])', text):
        quoted, bare = match.groups()
        tokens.append(quoted if quoted is not None else bare)
    return tokens


def workshop_item_metadata(acf_path: Path, workshop_id: str) -> dict:
    parsed = parse_keyvalues_object(acf_path.read_text(encoding="utf-8", errors="replace"))
    app_workshop = parsed.get("AppWorkshop")
    if not isinstance(app_workshop, dict):
        raise ValueError(f"Missing AppWorkshop object in {acf_path}")

    installed = app_workshop.get("WorkshopItemsInstalled")
    if not isinstance(installed, dict):
        raise ValueError(f"Missing WorkshopItemsInstalled object in {acf_path}")

    item = installed.get(workshop_id)
    if not isinstance(item, dict):
        raise ValueError(f"Missing workshop item {workshop_id} in {acf_path}")
    return item


def uiod_version_from_workshop_acf(acf_path: Path, workshop_id: str) -> str:
    metadata = workshop_item_metadata(acf_path, workshop_id)
    time_updated = metadata.get("timeupdated")
    if time_updated is None:
        raise ValueError(f"Workshop item {workshop_id} is missing timeupdated in {acf_path}")
    return timestamp_version(int(time_updated))


def descriptor_value(path: Path, key: str) -> str | None:
    import re

    pattern = re.compile(rf'^\s*{re.escape(key)}\s*=\s*"([^"]+)"\s*$', re.MULTILINE)
    match = pattern.search(path.read_text(encoding="utf-8-sig", errors="replace"))
    return match.group(1) if match else None


def uiod_version_from_descriptor(path: Path) -> str:
    version = descriptor_value(path, "version")
    if version is None:
        raise ValueError(f"Descriptor is missing version: {path}")
    return version


def stellaris_version_from_descriptor(path: Path) -> str:
    supported_version = descriptor_value(path, "supported_version")
    if supported_version is None:
        raise ValueError(f"Descriptor is missing supported_version: {path}")
    return supported_version


def uiod_version_from_file(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return f"sha-{digest}"


def render_badge_section(index: dict, metadata: dict) -> str:
    badges = index.get("badges")
    if not isinstance(badges, list) or not badges:
        raise ValueError("Badge index must contain a non-empty badges array.")

    badge_markdown = []

    for badge in badges:
        field = badge["metadata_field"]
        if field not in metadata:
            raise ValueError(f"Badge {badge['id']} references missing metadata field: {field}")

        label = badge["label"]
        value = str(metadata[field])
        url = badge_url(label, value, badge.get("color", "blue"))
        badge_markdown.append(f"![{label}: {value}]({url})")

    return " ".join(badge_markdown)


def render_badge_docs(index: dict) -> str:
    badges = index.get("badges")
    if not isinstance(badges, list) or not badges:
        raise ValueError("Badge index must contain a non-empty badges array.")

    table_lines = [
        "| Badge | Metadata field | Source | Logic |",
        "| --- | --- | --- | --- |",
    ]

    for badge in badges:
        field = badge["metadata_field"]
        label = badge["label"]
        table_lines.append(
            f"| {label} | `{field}` | {badge['source']} | {badge['logic']} |"
        )

    lines = [
        f"# {index.get('docs_heading', 'Status Badges')}",
        "",
        "The README displays these badges near the top of the page. They are generated from `badges/index.json` and `badges/metadata.json`.",
        "",
        "Run `python scripts/update_status_badges.py` after changing badge definitions or metadata.",
        "",
        *table_lines,
        "",
    ]
    return "\n".join(lines)


def replace_generated_section(readme: str, index: dict, section: str) -> str:
    start_marker = index["start_marker"]
    end_marker = index["end_marker"]
    generated = f"{start_marker}\n{section}\n{end_marker}"

    if start_marker in readme and end_marker in readme:
        before, remainder = readme.split(start_marker, 1)
        _, after = remainder.split(end_marker, 1)
        return f"{before}{generated}{after}"

    first_heading = "\n## "
    insert_index = readme.find(first_heading)
    if insert_index == -1:
        return f"{readme.rstrip()}\n\n{generated}\n"

    return f"{readme[:insert_index]}\n\n{generated}\n{readme[insert_index:]}"


def update_metadata(
    metadata: dict,
    sync_status: str | None,
    version: str | None,
    uiod_version: str | None,
    stellaris_version: str | None,
) -> dict:
    metadata = dict(metadata)
    if version is not None:
        metadata["version"] = version
    if uiod_version is not None:
        metadata["uiod_version"] = uiod_version
    if stellaris_version is not None:
        metadata["stellaris_version"] = stellaris_version
    if sync_status is not None:
        metadata["sync_status"] = sync_status
    return metadata


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render generated status badges into README.md.")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX, help="Badge index path.")
    parser.add_argument("--version", help="Internal date/time version value to write before rendering.")
    parser.add_argument(
        "--version-now",
        action="store_true",
        help="Set the internal version to the current UTC date/time before rendering.",
    )
    parser.add_argument("--uiod-version", help="UIOD upstream version value to write before rendering.")
    parser.add_argument("--stellaris-version", help="Stellaris supported version value to write before rendering.")
    parser.add_argument(
        "--uiod-descriptor",
        type=Path,
        help="Downloaded descriptor.mod used to derive uiod_version from the upstream mod version field.",
    )
    parser.add_argument(
        "--workshop-acf",
        type=Path,
        help="Steam appworkshop ACF file used to derive uiod_version from the workshop timeupdated value.",
    )
    parser.add_argument(
        "--uiod-workshop-id",
        default=DEFAULT_UIOD_WORKSHOP_ID,
        help=f"Workshop ID to read from --workshop-acf. Defaults to {DEFAULT_UIOD_WORKSHOP_ID}.",
    )
    parser.add_argument(
        "--uiod-file-fallback",
        type=Path,
        help="File used to derive a stable content-hash uiod_version when --workshop-acf is unavailable.",
    )
    parser.add_argument("--sync-status", help="Optional sync_status metadata value to write before rendering.")
    parser.add_argument("--check", action="store_true", help="Fail if README.md or metadata would change.")
    return parser.parse_args()


def configured_docs_path(index: dict) -> Path | None:
    return resolve_repo_path(index["docs_path"]) if "docs_path" in index else None


def derive_descriptor_versions(args: argparse.Namespace) -> tuple[str | None, str | None]:
    if args.uiod_descriptor is None:
        return args.uiod_version, args.stellaris_version

    descriptor_path = resolve_repo_path(str(args.uiod_descriptor))
    if descriptor_path.exists():
        return uiod_version_from_descriptor(descriptor_path), stellaris_version_from_descriptor(descriptor_path)

    if args.workshop_acf is None and args.uiod_file_fallback is None:
        raise FileNotFoundError(f"UIOD descriptor not found: {descriptor_path}")
    return args.uiod_version, args.stellaris_version


def derive_workshop_version(args: argparse.Namespace, uiod_version: str | None) -> str | None:
    if uiod_version is not None or args.workshop_acf is None:
        return uiod_version

    acf_path = resolve_repo_path(str(args.workshop_acf))
    if acf_path.exists():
        return uiod_version_from_workshop_acf(acf_path, args.uiod_workshop_id)

    if args.uiod_file_fallback is None:
        raise FileNotFoundError(f"Workshop ACF file not found: {acf_path}")
    return uiod_version


def derive_file_fallback_version(args: argparse.Namespace, uiod_version: str | None) -> str | None:
    if uiod_version is not None or args.uiod_file_fallback is None:
        return uiod_version
    return uiod_version_from_file(resolve_repo_path(str(args.uiod_file_fallback)))


def derive_versions(args: argparse.Namespace) -> tuple[str | None, str | None, str | None]:
    version = current_timestamp_version() if args.version_now else args.version
    uiod_version, stellaris_version = derive_descriptor_versions(args)
    uiod_version = derive_workshop_version(args, uiod_version)
    uiod_version = derive_file_fallback_version(args, uiod_version)
    return version, uiod_version, stellaris_version


def render_outputs(
    index: dict,
    metadata: dict,
    readme_path: Path,
    docs_path: Path | None,
) -> tuple[str, str, str | None, str | None]:
    section = render_badge_section(index, metadata)
    current_readme = readme_path.read_text(encoding="utf-8")
    next_readme = replace_generated_section(current_readme, index, section)
    next_docs = render_badge_docs(index) if docs_path is not None else None
    current_docs = read_existing_text(docs_path)
    return current_readme, next_readme, current_docs, next_docs


def read_existing_text(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def outputs_changed(
    current_metadata: dict,
    metadata: dict,
    current_readme: str,
    next_readme: str,
    current_docs: str | None,
    next_docs: str | None,
) -> bool:
    return any(
        (
            current_metadata != metadata,
            current_readme != next_readme,
            current_docs != next_docs,
        )
    )


def write_outputs(
    metadata_path: Path,
    metadata: dict,
    readme_path: Path,
    next_readme: str,
    docs_path: Path | None,
    next_docs: str | None,
) -> None:
    write_json(metadata_path, metadata)
    readme_path.write_text(next_readme, encoding="utf-8", newline="\n")
    if docs_path is not None and next_docs is not None:
        docs_path.write_text(next_docs, encoding="utf-8", newline="\n")


def main() -> int:
    args = parse_args()
    index_path = resolve_repo_path(str(args.index))
    index = load_json(index_path)
    metadata_path = resolve_repo_path(index["metadata_path"])
    readme_path = resolve_repo_path(index["readme_path"])
    docs_path = configured_docs_path(index)

    version, uiod_version, stellaris_version = derive_versions(args)
    metadata = update_metadata(
        load_json(metadata_path),
        args.sync_status,
        version,
        uiod_version,
        stellaris_version,
    )
    current_readme, next_readme, current_docs, next_docs = render_outputs(index, metadata, readme_path, docs_path)

    if args.check:
        current_metadata = load_json(metadata_path)
        if outputs_changed(current_metadata, metadata, current_readme, next_readme, current_docs, next_docs):
            print("Generated status badges are out of date.")
            return 1
        print("Generated status badges are up to date.")
        return 0

    write_outputs(metadata_path, metadata, readme_path, next_readme, docs_path, next_docs)
    print(f"Updated status badges from {display_path(index_path)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
