from __future__ import annotations

from collections import defaultdict

from archgen.detection import SYSTEMS_CATEGORY_ORDER, Detection


def format_summary(summary) -> str:
    lines = [
        "Architecture Summary",
        f"Root: {summary.root}",
        f"Scanned files: {summary.scanned_files}",
        "Languages:",
    ]

    if summary.languages:
        lines.extend(
            f"  {language}: {count}"
            for language, count in sorted(summary.languages.items())
        )
    else:
        lines.append("  None")

    lines.append("Notable files:")
    if summary.notable_files:
        lines.extend(f"  {path.as_posix()}" for path in summary.notable_files)
    else:
        lines.append("  None")

    lines.append("C/C++ files:")
    lines.append(f"  Sources: {len(summary.c_cpp_sources)}")
    if summary.c_cpp_sources:
        lines.extend(f"    {path.as_posix()}" for path in summary.c_cpp_sources)
    else:
        lines.append("    None")

    lines.append(f"  Headers: {len(summary.c_cpp_headers)}")
    if summary.c_cpp_headers:
        lines.extend(f"    {path.as_posix()}" for path in summary.c_cpp_headers)
    else:
        lines.append("    None")

    lines.append("C/C++ build files:")
    lines.append("  Makefiles:")
    if summary.c_cpp_build.makefiles:
        lines.extend(f"    {path.as_posix()}" for path in summary.c_cpp_build.makefiles)
    else:
        lines.append("    None")
    lines.append("  CMake files:")
    if summary.c_cpp_build.cmake_files:
        lines.extend(f"    {path.as_posix()}" for path in summary.c_cpp_build.cmake_files)
    else:
        lines.append("    None")
    lines.append("  Compile commands:")
    if summary.c_cpp_build.compile_commands_files:
        lines.extend(
            f"    {path.as_posix()}"
            for path in summary.c_cpp_build.compile_commands_files
        )
    else:
        lines.append("    None")
    lines.append("  Make targets:")
    if summary.c_cpp_build.make_targets:
        lines.extend(
            f"    {target.source.as_posix()} -> {target.name}"
            for target in summary.c_cpp_build.make_targets
        )
    else:
        lines.append("    None")
    lines.append("  CMake targets:")
    if summary.c_cpp_build.cmake_targets:
        lines.extend(
            f"    {target.source.as_posix()} -> {target.name}"
            for target in summary.c_cpp_build.cmake_targets
        )
    else:
        lines.append("    None")

    lines.append("C/C++ project shape:")
    looks_like_project = "Yes" if summary.c_cpp_project_shape.looks_like_project else "No"
    lines.append(f"  Looks like C/C++ project: {looks_like_project}")
    lines.append("  Evidence:")
    lines.append(f"    Source files: {len(summary.c_cpp_sources)}")
    lines.append(f"    Header files: {len(summary.c_cpp_headers)}")
    lines.append("    Build files:")
    if summary.c_cpp_project_shape.build_files:
        lines.extend(
            f"      {path.as_posix()}"
            for path in summary.c_cpp_project_shape.build_files
        )
    else:
        lines.append("      None")
    lines.append("    Conventional directories:")
    if summary.c_cpp_project_shape.conventional_dirs:
        lines.extend(
            f"      {path.as_posix()}/"
            for path in summary.c_cpp_project_shape.conventional_dirs
        )
    else:
        lines.append("      None")

    lines.append("C/C++ local includes:")
    lines.append(f"  Relationships: {len(summary.c_cpp_local_includes)}")
    if summary.c_cpp_local_includes:
        lines.extend(
            f"    {include.source.as_posix()} -> {include.included_path}"
            for include in summary.c_cpp_local_includes
        )
    else:
        lines.append("    None")

    lines.append("C/C++ systems patterns:")
    if summary.c_cpp_systems_patterns:
        for category in SYSTEMS_CATEGORY_ORDER:
            category_matches = [
                match
                for match in summary.c_cpp_systems_patterns
                if match.category == category
            ]
            if not category_matches:
                continue
            lines.append(f"  {category}:")
            lines.extend(
                f"    {match.source.as_posix()} -> {match.pattern}"
                for match in category_matches
            )
    else:
        lines.append("  None")

    lines.append("C/C++ CLI binary evidence:")
    if summary.c_cpp_cli_binary_evidence:
        lines.extend(
            f"  {item.source.as_posix()} -> {', '.join(item.signals)}"
            for item in summary.c_cpp_cli_binary_evidence
        )
    else:
        lines.append("  None")

    lines.append("Detected components:")
    if summary.detections:
        lines.extend(format_detections(summary.detections))
    else:
        lines.append("  None")

    return "\n".join(lines)


def format_detections(detections: list[Detection]) -> list[str]:
    lines: list[str] = []
    detections_by_kind: dict[str, list[Detection]] = defaultdict(list)
    for detection in detections:
        detections_by_kind[detection.kind].append(detection)

    for kind in sorted(detections_by_kind):
        lines.append(f"  {kind}:")
        for detection in sorted(
            detections_by_kind[kind],
            key=lambda item: (item.name, item.evidence),
        ):
            confidence = (
                ""
                if detection.confidence is None
                else f" (confidence: {detection.confidence:.2f})"
            )
            lines.append(f"    {detection.name}{confidence}")
            lines.append("      Evidence:")
            if detection.evidence:
                lines.extend(
                    f"        {path.as_posix()}" for path in detection.evidence
                )
            else:
                lines.append("        None")

    return lines
