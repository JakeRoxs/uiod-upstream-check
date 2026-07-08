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

    required_fields = {"display_name", "workshop_id", "upstream_file", "vendor_path", "patched_path"}
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
        return 0

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
        print(f"{variant}: updated vendored baseline: {vendored_path}")
        print(f"{variant}: regenerated patched GUI: {patched_path}")
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
        "--check-generated",
        action="store_true",
        help="Verify patched output equals vendored baseline plus the spacebar pause patch.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        manifest = load_manifest(args.manifest)
    except (OSError, ValueError) as error:
        print(f"Failed to load manifest: {error}", file=sys.stderr)
        return 1

    if args.all:
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

    if not args.variant:
        print("--variant is required unless --all is used.", file=sys.stderr)
        return 1
    if args.variant not in manifest:
        available = ", ".join(sorted(manifest))
        print(f"Unknown variant {args.variant}. Available variants: {available}", file=sys.stderr)
        return 1

    config = manifest[args.variant]
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


if __name__ == "__main__":
    raise SystemExit(main())
