import math
from collections import Counter
from typing import Any, Iterable, Tuple
import os
import ezdxf
from ezdxf import recover


# -----------------------------
# CONFIG
# -----------------------------
DEFAULT_PRECISION = 6
DEFAULT_COMPARE_TYPES = {
    "LINE",
    "CIRCLE",
    "ARC",
    "LWPOLYLINE",
    "POLYLINE",
    "POINT",
    "ELLIPSE",
    "SPLINE",
    "TEXT",
    "MTEXT",
    "INSERT",
}


# -----------------------------
# HELPERS
# -----------------------------
def _r(value: Any, precision: int = DEFAULT_PRECISION) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if math.isfinite(float(value)):
            return round(float(value), precision)
        return value
    return value


def _pt(point: Any, precision: int = DEFAULT_PRECISION) -> Tuple[Any, Any, Any]:
    if point is None:
        return (None, None, None)
    return (
        _r(point[0], precision),
        _r(point[1], precision),
        _r(point[2], precision),
    )


def _normalize_text(text: Any) -> str:
    if text is None:
        return ""
    return " ".join(str(text).split()).strip()


def _safe_layer(entity: Any) -> str:
    try:
        return entity.dxf.layer
    except Exception:
        return ""


def _safe_color(entity: Any) -> Any:
    try:
        return entity.dxf.color
    except Exception:
        return None


def _safe_linetype(entity: Any) -> str:
    try:
        return entity.dxf.linetype
    except Exception:
        return ""


def _base_signature(entity: Any) -> Tuple[Any, ...]:
    return (
        entity.dxftype(),
        _safe_layer(entity),
        _safe_color(entity),
        _safe_linetype(entity),
    )


# -----------------------------
# ENTITY NORMALIZERS
# -----------------------------
def _normalize_line(entity: Any, precision: int) -> Tuple[Any, ...]:
    start = _pt(entity.dxf.start, precision)
    end = _pt(entity.dxf.end, precision)

    # Make direction-independent
    if start <= end:
        p1, p2 = start, end
    else:
        p1, p2 = end, start

    return _base_signature(entity) + (p1, p2)


def _normalize_circle(entity: Any, precision: int) -> Tuple[Any, ...]:
    return _base_signature(entity) + (
        _pt(entity.dxf.center, precision),
        _r(entity.dxf.radius, precision),
    )


def _normalize_arc(entity: Any, precision: int) -> Tuple[Any, ...]:
    return _base_signature(entity) + (
        _pt(entity.dxf.center, precision),
        _r(entity.dxf.radius, precision),
        _r(entity.dxf.start_angle % 360.0, precision),
        _r(entity.dxf.end_angle % 360.0, precision),
    )


def _normalize_lwpolyline(entity: Any, precision: int) -> Tuple[Any, ...]:
    points = []
    for v in entity.get_points("xyb"):
        x, y, bulge = v
        points.append((_r(x, precision), _r(y, precision), _r(bulge, precision)))

    closed = int(entity.closed)

    return _base_signature(entity) + (
        closed,
        tuple(points),
    )


def _normalize_polyline(entity: Any, precision: int) -> Tuple[Any, ...]:
    points = []
    try:
        for v in entity.vertices:
            points.append(_pt(v.dxf.location, precision))
    except Exception:
        for v in entity.points():
            points.append(_pt(v, precision))

    closed = 0
    try:
        closed = int(entity.is_closed)
    except Exception:
        pass

    return _base_signature(entity) + (
        closed,
        tuple(points),
    )


def _normalize_point(entity: Any, precision: int) -> Tuple[Any, ...]:
    return _base_signature(entity) + (
        _pt(entity.dxf.location, precision),
    )


def _normalize_ellipse(entity: Any, precision: int) -> Tuple[Any, ...]:
    return _base_signature(entity) + (
        _pt(entity.dxf.center, precision),
        _pt(entity.dxf.major_axis, precision),
        _r(entity.dxf.ratio, precision),
        _r(entity.dxf.start_param, precision),
        _r(entity.dxf.end_param, precision),
    )


def _normalize_spline(entity: Any, precision: int) -> Tuple[Any, ...]:
    control_points = []
    fit_points = []

    try:
        for p in entity.control_points:
            control_points.append(_pt(p, precision))
    except Exception:
        pass

    try:
        for p in entity.fit_points:
            fit_points.append(_pt(p, precision))
    except Exception:
        pass

    degree = None
    try:
        degree = entity.dxf.degree
    except Exception:
        pass

    closed = 0
    try:
        closed = int(entity.closed)
    except Exception:
        pass

    return _base_signature(entity) + (
        _r(degree, precision),
        closed,
        tuple(control_points),
        tuple(fit_points),
    )


def _normalize_text_entity(entity: Any, precision: int) -> Tuple[Any, ...]:
    insert = None
    rotation = None
    height = None
    text = ""

    try:
        insert = _pt(entity.dxf.insert, precision)
    except Exception:
        pass

    try:
        rotation = _r(entity.dxf.rotation, precision)
    except Exception:
        pass

    try:
        height = _r(entity.dxf.height, precision)
    except Exception:
        pass

    try:
        text = _normalize_text(entity.dxf.text)
    except Exception:
        try:
            text = _normalize_text(entity.text)
        except Exception:
            text = ""

    return _base_signature(entity) + (
        text,
        insert,
        rotation,
        height,
    )


def _normalize_mtext(entity: Any, precision: int) -> Tuple[Any, ...]:
    insert = None
    char_height = None
    rotation = None
    text = ""

    try:
        insert = _pt(entity.dxf.insert, precision)
    except Exception:
        pass

    try:
        char_height = _r(entity.dxf.char_height, precision)
    except Exception:
        pass

    try:
        rotation = _r(entity.get_rotation(), precision)
    except Exception:
        try:
            rotation = _r(entity.dxf.rotation, precision)
        except Exception:
            rotation = None

    try:
        text = _normalize_text(entity.text)
    except Exception:
        text = ""

    return _base_signature(entity) + (
        text,
        insert,
        rotation,
        char_height,
    )


def _normalize_insert(entity: Any, precision: int) -> Tuple[Any, ...]:
    name = ""
    insert = None
    rotation = None
    xscale = 1.0
    yscale = 1.0
    zscale = 1.0

    try:
        name = entity.dxf.name
    except Exception:
        pass

    try:
        insert = _pt(entity.dxf.insert, precision)
    except Exception:
        pass

    try:
        rotation = _r(entity.dxf.rotation, precision)
    except Exception:
        pass

    try:
        xscale = _r(entity.dxf.xscale, precision)
    except Exception:
        pass

    try:
        yscale = _r(entity.dxf.yscale, precision)
    except Exception:
        pass

    try:
        zscale = _r(entity.dxf.zscale, precision)
    except Exception:
        pass

    attribs = []
    try:
        for a in entity.attribs:
            attribs.append(
                (
                    getattr(a.dxf, "tag", ""),
                    _normalize_text(getattr(a.dxf, "text", "")),
                    _pt(getattr(a.dxf, "insert", None), precision),
                )
            )
    except Exception:
        pass

    attribs.sort()

    return _base_signature(entity) + (
        name,
        insert,
        rotation,
        xscale,
        yscale,
        zscale,
        tuple(attribs),
    )


def _normalize_entity(entity: Any, precision: int = DEFAULT_PRECISION) -> Tuple[Any, ...] | None:
    entity_type = entity.dxftype()

    if entity_type == "LINE":
        return _normalize_line(entity, precision)
    if entity_type == "CIRCLE":
        return _normalize_circle(entity, precision)
    if entity_type == "ARC":
        return _normalize_arc(entity, precision)
    if entity_type == "LWPOLYLINE":
        return _normalize_lwpolyline(entity, precision)
    if entity_type == "POLYLINE":
        return _normalize_polyline(entity, precision)
    if entity_type == "POINT":
        return _normalize_point(entity, precision)
    if entity_type == "ELLIPSE":
        return _normalize_ellipse(entity, precision)
    if entity_type == "SPLINE":
        return _normalize_spline(entity, precision)
    if entity_type == "TEXT":
        return _normalize_text_entity(entity, precision)
    if entity_type == "MTEXT":
        return _normalize_mtext(entity, precision)
    if entity_type == "INSERT":
        return _normalize_insert(entity, precision)

    return None


# -----------------------------
# PUBLIC API
# -----------------------------

def extract_normalized_entities(
    dxf_path: str,
    precision: int = DEFAULT_PRECISION,
    include_types=None,
):
    if include_types is None:
        include_types = DEFAULT_COMPARE_TYPES

    include_types = set(include_types)

    if os.path.isdir(dxf_path):
        raise ValueError(f"Expected a DXF file path, got directory: {dxf_path}")

    if not os.path.isfile(dxf_path):
        raise FileNotFoundError(f"DXF file not found: {dxf_path}")

    # First try normal load
    try:
        doc = ezdxf.readfile(dxf_path)

    # If DXF is malformed, recover it
    except Exception:
        doc, auditor = recover.readfile(dxf_path)

        # Optional: skip files that are too broken
        if auditor.has_errors:
            print(f"[RECOVERED WITH ERRORS] {dxf_path}")
            for err in auditor.errors[:10]:
                print("   ", err)

    msp = doc.modelspace()
    normalized = []

    for entity in msp:
        try:
            if entity.dxftype() not in include_types:
                continue

            item = _normalize_entity(entity, precision)
            if item is not None:
                normalized.append(item)

        except Exception as e:
            print(f"[SKIPPED ENTITY] {dxf_path} | {entity.dxftype()} | {e}")

    normalized.sort()
    return normalized

def compare_dxf_geometry(
    file_a: str,
    file_b: str,
    precision: int = DEFAULT_PRECISION,
    include_types: Iterable[str] | None = None,
) -> dict[str, Any]:
    entities_a = extract_normalized_entities(file_a, precision, include_types)
    entities_b = extract_normalized_entities(file_b, precision, include_types)

    counter_a = Counter(entities_a)
    counter_b = Counter(entities_b)

    only_in_a = list((counter_a - counter_b).elements())
    only_in_b = list((counter_b - counter_a).elements())

    return {
        "match": len(only_in_a) == 0 and len(only_in_b) == 0,
        "count_a": len(entities_a),
        "count_b": len(entities_b),
        "only_in_a": only_in_a,
        "only_in_b": only_in_b,
    }



def get_dxf_files(folder):
    return {
        f.lower(): os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith(".dxf")
    }


def compare_dxf_folders(folder_a, folder_b, precision=6):
    files_a = get_dxf_files(folder_a)
    files_b = get_dxf_files(folder_b)

    all_names = sorted(set(files_a.keys()) | set(files_b.keys()))
    results = []

    for name in all_names:
        path_a = files_a.get(name)
        path_b = files_b.get(name)

        if path_a and path_b:
            try:
                result = compare_dxf_geometry(
                    path_a,
                    path_b,
                    precision=precision
                )

                results.append({
                    "file": name,
                    "status": "MATCH" if result["match"] else "DIFFERENT",
                    "count_a": result["count_a"],
                    "count_b": result["count_b"],
                    "diff_a": len(result["only_in_a"]),
                    "diff_b": len(result["only_in_b"]),
                })

            except Exception as e:
                results.append({
                    "file": name,
                    "status": "ERROR",
                    "error": str(e),
                })

        elif path_a:
            results.append({
                "file": name,
                "status": "ONLY_IN_A",
            })
        else:
            results.append({
                "file": name,
                "status": "ONLY_IN_B",
            })

    return results

# Step 4: Define visual overlay function
def plot_dxf(file_path, color, ax, alpha=0.6, linewidth=2):
    try:
        doc = ezdxf.readfile(file_path)
        msp = doc.modelspace()

        for entity in msp:
            if entity.dxftype() == 'LINE':
                start = entity.dxf.start
                end = entity.dxf.end
                ax.plot([start.x, end.x], [start.y, end.y], color=color, alpha=alpha, linewidth=linewidth)

            elif entity.dxftype() == 'CIRCLE':
                center = entity.dxf.center
                radius = entity.dxf.radius
                circle = Circle((center.x, center.y), radius, color=color, fill=False, alpha=alpha, linewidth=linewidth)
                ax.add_patch(circle)

            elif entity.dxftype() == 'ARC':
                center = entity.dxf.center
                radius = entity.dxf.radius
                start_angle = entity.dxf.start_angle
                end_angle = entity.dxf.end_angle
                arc = Arc((center.x, center.y), 2*radius, 2*radius,
                          angle=0, theta1=start_angle, theta2=end_angle,
                          color=color, alpha=alpha, linewidth=linewidth)
                ax.add_patch(arc)

    except Exception as e:
        print(f"⚠️ Failed to plot {file_path}: {e}")

def overlay_dxf(qa_file, prd_file, title):
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Using cyan and magenta for better contrast
    plot_dxf(prd_file, '#00FFFF', ax, alpha=0.6, linewidth=2)  # Cyan for PRD
    plot_dxf(qa_file, '#FF00FF', ax, alpha=0.6, linewidth=2)   # Magenta for QA
    
    ax.set_aspect('equal')
    ax.set_title(f"Overlay for {title}\nCyan = PRD, Magenta = QA")
    
    # Legend patches
    from matplotlib.patches import Patch
    legend_patches = [
        Patch(color='#00FFFF', label='301 (Cyan)', alpha=0.6),
        Patch(color='#FF00FF', label='300 (Magenta)', alpha=0.6)
    ]
    ax.legend(handles=legend_patches, loc='upper right')
    # Save the figure as JPG in the output folder
    output_path = os.path.join(output_folder, f"{title}_diff.jpg")
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.show()

if __name__ == "__main__":
    folder_a = r"300/out"
    folder_b = r"301/out"

    results = compare_dxf_folders(folder_a, folder_b, precision=6)

    for r in results:
        if r["status"] == "MATCH":
            with open('outN.txt',"a",encoding="utf-8")as file:
                file.write(f"✅ {r['file']}\n")
        elif r["status"] == "DIFFERENT":
            with open('outN.txt',"a",encoding="utf-8")as file:
                file.write(f"❌ {r['file']} | ΔA:{r['diff_a']} ΔB:{r['diff_b']}\n")
        else:
            with open('outN.txt',"a",encoding="utf-8")as file:
                file.write(f"⚠️ {r['file']} - {r['status']}\n")
    print(results[175])