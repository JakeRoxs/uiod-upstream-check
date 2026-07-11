import argparse
import difflib
import json
import re
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "variants.json"


def normalize_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text if text.endswith("\n") else text + "\n"


def apply_spacebar_pause_patch(upstream_text: str, remove_pause_clicksound: bool = False) -> str:
    lines = upstream_text.splitlines(keepends=True)
    if remove_pause_clicksound:
        lines = [
            line
            for line in lines
            if not re.match(r"^\s*clicksound\s*=\s*\"ui_click_pause\"(?:\s*#.*)?$", line)
        ]

    name_index = next(
        (
            index
            for index, line in enumerate(lines)
            if re.match(r"^\s*name\s*=\s*\"start_stop_icons\"(?:\s*#.*)?$", line)
        ),
        None,
    )
    if name_index is None:
        raise ValueError("Could not find the start_stop_icons pause button in upstream GUI.")

    start_index = None
    for index in range(name_index - 1, -1, -1):
        if re.match(r"^\s*buttonType\s*=\s*\{\s*(?:#.*)?$", lines[index]):
            start_index = index
            break

    if start_index is None:
        raise ValueError("Could not find the start_stop_icons buttonType block start.")

    depth = 0
    end_index = None
    for index in range(start_index, len(lines)):
        depth += lines[index].count("{")
        depth -= lines[index].count("}")
        if depth == 0:
            end_index = index
            break

    if end_index is None:
        raise ValueError("Could not find the start_stop_icons buttonType block end.")

    replacement_index = next(
        (
            index
            for index in range(name_index + 1, end_index)
            if re.match(r"^\s*alwaysTransparent\s*=\s*yes(?:\s*#.*)?$", lines[index])
        ),
        None,
    )
    if replacement_index is None:
        raise ValueError(
            "Could not find alwaysTransparent = yes in the start_stop_icons buttonType block."
        )

    indent = lines[replacement_index][
        : len(lines[replacement_index]) - len(lines[replacement_index].lstrip())
    ]
    newline = "\r\n" if lines[replacement_index].endswith("\r\n") else "\n"
    lines[replacement_index : replacement_index + 1] = [
        f"{indent}frame = 1{newline}",
        f'{indent}shortcut = "SPACE"{newline}',
    ]

    return "".join(lines)


def unified_diff(expected: str, actual: str, expected_path: str, actual_path: str) -> str:
    return "".join(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile=expected_path,
            tofile=actual_path,
        )
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def load_manifest(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        manifest = json.load(file)

    if not isinstance(manifest, dict) or not manifest:
        raise ValueError(f"Manifest must contain at least one variant: {path}")

    required_fields = {"display_name", "workshop_id", "upstream_file", "vendor_path", "patched_path", "mod_path"}
    for variant, config in manifest.items():
        missing = required_fields - set(config)
        if missing:
            missing_fields = ", ".join(sorted(missing))
            raise ValueError(f"Variant {variant} is missing fields: {missing_fields}")

    return manifest


def variant_paths(config: dict, vendored_override: Path | None, patched_override: Path | None) -> tuple[Path, Path]:
    vendored_path = vendored_override or ROOT / config["vendor_path"]
    patched_path = patched_override or ROOT / config["patched_path"]
    return vendored_path, patched_path


def mod_gui_path(config: dict) -> Path | None:
    mod_path = config.get("mod_path")
    if not mod_path:
        return None
    return ROOT / mod_path / config["upstream_file"]


def descriptor_value(text: str, key: str) -> str | None:
    pattern = re.compile(rf'^\s*{re.escape(key)}\s*=\s*"([^"]+)"', re.MULTILINE)
    match = pattern.search(text)
    return match.group(1) if match else None


def expected_mod_name(config: dict) -> str | None:
    mod_path = config.get("mod_path")
    return Path(mod_path).name if mod_path else None


def validate_descriptor_metadata(variant: str, config: dict, descriptor_text: str) -> int:
    expected_name = expected_mod_name(config)
    if expected_name is None:
        return 0

    actual_name = descriptor_value(descriptor_text, "name")
    if actual_name != expected_name:
        print(
            f'{variant}: descriptor.mod name mismatch. Expected "{expected_name}", found "{actual_name}".',
            file=sys.stderr,
        )
        return 1

    expected_remote_file_id = config.get("published_workshop_id")
    if expected_remote_file_id:
        actual_remote_file_id = descriptor_value(descriptor_text, "remote_file_id")
        if actual_remote_file_id != expected_remote_file_id:
            print(
                f'{variant}: descriptor.mod remote_file_id mismatch. Expected "{expected_remote_file_id}", found "{actual_remote_file_id}".',
                file=sys.stderr,
            )
            return 1

    return 0


def check_full_mod_stack(variant: str, config: dict, patched_text: str) -> int:
    target = mod_gui_path(config)
    if target is None:
        return 0

    mod_root = target.parents[len(Path(config["upstream_file"]).parts) - 1]
    descriptor = mod_root / "descriptor.mod"
    if not descriptor.exists():
        print(f"{variant}: generated mod folder is missing descriptor.mod: {descriptor}", file=sys.stderr)
        return 1
    if not target.exists():
        print(f"{variant}: generated mod GUI not found: {target}", file=sys.stderr)
        return 1

    actual = normalize_text(target)
    if actual != patched_text:
        print(f"{variant}: generated mod GUI is out of sync with patched output.", file=sys.stderr)
        print(unified_diff(patched_text, actual, config["patched_path"], str(target)), file=sys.stderr)
        return 1

    descriptor_text = descriptor.read_text(encoding="utf-8-sig")
    if validate_descriptor_metadata(variant, config, descriptor_text) != 0:
        return 1

    picture_match = re.search(r'^\s*picture\s*=\s*"([^"]+)"', descriptor_text, re.MULTILINE)
    if picture_match and not (mod_root / picture_match.group(1)).exists():
        print(f"{variant}: generated mod folder is missing picture file: {picture_match.group(1)}", file=sys.stderr)
        return 1

    print(f"{variant}: generated mod folder matches patched output.")
    return 0


def write_full_mod_stack(config: dict, patched_text: str) -> Path | None:
    target = mod_gui_path(config)
    if target is None:
        return None
    write_text(target, patched_text)
    return target


def check_generated(variant: str, config: dict, vendored_path: Path, patched_path: Path) -> int:
    if not vendored_path.exists():
        print(f"Vendored GUI not found for {variant}: {vendored_path}", file=sys.stderr)
        return 1
    if not patched_path.exists():
        print(f"Patched GUI not found for {variant}: {patched_path}", file=sys.stderr)
        return 1

    try:
        expected = apply_spacebar_pause_patch(
            normalize_text(vendored_path),
            remove_pause_clicksound=bool(config.get("remove_pause_clicksound", False)),
        )
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1

    actual = normalize_text(patched_path)
    if expected == actual:
        print(f"{variant}: patched GUI matches vendored baseline plus patch.")
        return check_full_mod_stack(variant, config, actual)

    print(f"{variant}: patched GUI is out of date.", file=sys.stderr)
    print(
        unified_diff(expected, actual, f"{vendored_path} + spacebar patch", str(patched_path)),
        file=sys.stderr,
    )
    return 1


def check_or_update_upstream(
    variant: str,
    config: dict,
    upstream_path: Path,
    vendored_path: Path,
    patched_path: Path,
    local_path: Path | None,
    update: bool,
) -> int:
    if not upstream_path.exists():
        print(f"Upstream GUI not found for {variant}: {upstream_path}", file=sys.stderr)
        return 1

    if not update and not vendored_path.exists():
        print(f"Vendored GUI not found for {variant}: {vendored_path}", file=sys.stderr)
        return 1

    if local_path is not None and not local_path.exists():
        print(f"Local patched GUI not found for {variant}: {local_path}", file=sys.stderr)
        return 1

    upstream = normalize_text(upstream_path)
    vendored = normalize_text(vendored_path) if vendored_path.exists() else ""

    try:
        patched = apply_spacebar_pause_patch(
            upstream,
            remove_pause_clicksound=bool(config.get("remove_pause_clicksound", False)),
        )
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1

    if update:
        write_text(vendored_path, upstream)
        write_text(patched_path, patched)
        mod_target = write_full_mod_stack(config, patched)
        print(f"{variant}: updated vendored baseline: {vendored_path}")
        print(f"{variant}: regenerated patched GUI: {patched_path}")
        if mod_target is not None:
            print(f"{variant}: regenerated full mod GUI: {mod_target}")
        return 0

    if upstream != vendored:
        print(f"{variant}: current upstream GUI differs from the vendored baseline.", file=sys.stderr)
        print(unified_diff(vendored, upstream, str(vendored_path), str(upstream_path)), file=sys.stderr)
        return 1

    if local_path is None:
        print(f"{variant}: current upstream GUI matches the vendored baseline.")
        return 0

    actual = normalize_text(local_path)
    if patched == actual:
        print(f"{variant}: local patched GUI matches upstream plus patch.")
        return 0

    print(f"{variant}: unexpected local patched GUI differences detected.", file=sys.stderr)
    print(
        unified_diff(patched, actual, f"{vendored_path} + spacebar patch", str(local_path)),
        file=sys.stderr,
    )
    return 1


def workshop_upstream_path(workshop_root: Path, config: dict) -> Path:
    return workshop_root / config["workshop_id"] / config["upstream_file"]


def update_all_variants(manifest: dict, workshop_root: Path) -> int:
    results = []
    for variant, config in manifest.items():
        vendored_path, patched_path = variant_paths(config, None, None)
        results.append(
            check_or_update_upstream(
                variant,
                config,
                workshop_upstream_path(workshop_root, config),
                vendored_path,
                patched_path,
                None,
                True,
            )
        )
    return 0 if all(result == 0 for result in results) else 1


def managed_paths(manifest: dict) -> list[Path]:
    paths = []
    for config in manifest.values():
        paths.append(Path(config["vendor_path"]))
        paths.append(Path(config["patched_path"]))
        mod_path = config.get("mod_path")
        if mod_path:
            paths.append(Path(mod_path) / config["upstream_file"])
    return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check or update vendored UI Overhaul Dynamic GUI files and regenerate "
            "spacebar pause patched outputs."
        )
    )
    parser.add_argument(
        "upstream_gui",
        nargs="?",
        type=Path,
        help="Downloaded upstream GUI file path for --variant. Not needed with --check-generated.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"Variant manifest path. Defaults to {DEFAULT_MANIFEST}.",
    )
    parser.add_argument("--variant", help="Variant key from variants.json.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Apply --check-generated to every manifest variant.",
    )
    parser.add_argument(
        "--local-main-gui",
        type=Path,
        default=None,
        help="Optional local patched GUI path to verify against the generated patch.",
    )
    parser.add_argument(
        "--vendored-main-gui",
        type=Path,
        default=None,
        help="Override the selected variant's vendored upstream GUI path.",
    )
    parser.add_argument(
        "--patched-main-gui",
        type=Path,
        default=None,
        help="Override the selected variant's generated patched GUI path.",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update the vendored baseline and regenerate the patched GUI from upstream.",
    )
    parser.add_argument(
        "--update-all",
        action="store_true",
        help="Update every manifest variant from --workshop-root.",
    )
    parser.add_argument(
        "--workshop-root",
        type=Path,
        help="Steam workshop content root containing one directory per workshop item ID.",
    )
    parser.add_argument(
        "--list-managed-paths",
        action="store_true",
        help="Print manifest-managed GUI output paths, one per line.",
    )
    parser.add_argument(
        "--check-generated",
        action="store_true",
        help="Verify patched output equals vendored baseline plus the spacebar pause patch.",
    )
    return parser.parse_args()


def load_manifest_for_args(args: argparse.Namespace) -> dict | None:
    try:
        return load_manifest(args.manifest)
    except (OSError, ValueError) as error:
        print(f"Failed to load manifest: {error}", file=sys.stderr)
        return None


def list_managed_paths(manifest: dict) -> int:
    for path in managed_paths(manifest):
        print(path.as_posix())
    return 0


def run_update_all(args: argparse.Namespace, manifest: dict) -> int:
    if args.workshop_root is None:
        print("--workshop-root is required with --update-all.", file=sys.stderr)
        return 1
    if args.upstream_gui or args.variant or args.all or args.check_generated:
        print("--update-all cannot be combined with per-variant or check-generated options.", file=sys.stderr)
        return 1
    return update_all_variants(manifest, args.workshop_root)


def check_all_generated(args: argparse.Namespace, manifest: dict) -> int:
    if not args.check_generated:
        print("--all is only supported with --check-generated.", file=sys.stderr)
        return 1
    if args.vendored_main_gui or args.patched_main_gui or args.local_main_gui:
        print("Path overrides are not supported with --all.", file=sys.stderr)
        return 1

    results = []
    for variant, config in manifest.items():
        vendored_path, patched_path = variant_paths(config, None, None)
        results.append(check_generated(variant, config, vendored_path, patched_path))
    return 0 if all(result == 0 for result in results) else 1


def get_selected_variant_config(args: argparse.Namespace, manifest: dict) -> dict | None:
    if not args.variant:
        print("--variant is required unless --all is used.", file=sys.stderr)
        return None
    if args.variant not in manifest:
        available = ", ".join(sorted(manifest))
        print(f"Unknown variant {args.variant}. Available variants: {available}", file=sys.stderr)
        return None
    return manifest[args.variant]


def run_selected_variant(args: argparse.Namespace, manifest: dict) -> int:
    config = get_selected_variant_config(args, manifest)
    if config is None:
        return 1

    vendored_path, patched_path = variant_paths(config, args.vendored_main_gui, args.patched_main_gui)
    if args.check_generated:
        return check_generated(args.variant, config, vendored_path, patched_path)

    if args.upstream_gui is None:
        print("upstream_gui is required unless --check-generated is used.", file=sys.stderr)
        return 1

    return check_or_update_upstream(
        args.variant,
        config,
        args.upstream_gui,
        vendored_path,
        patched_path,
        args.local_main_gui,
        args.update,
    )


def main() -> int:
    args = parse_args()
    manifest = load_manifest_for_args(args)
    if manifest is None:
        return 1

    if args.list_managed_paths:
        return list_managed_paths(manifest)

    if args.update_all:
        return run_update_all(args, manifest)

    if args.all:
        return check_all_generated(args, manifest)

    return run_selected_variant(args, manifest)


if __name__ == "__main__":
    raise SystemExit(main())
