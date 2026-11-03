import os
import shutil
import re
import ezdxf
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Circle

# Define paths
folder_qa = "300/out"
folder_prd = "301/out"
output_folder = "Output"

# Step 1: Clear the output folder
if os.path.exists(output_folder):
    for f in os.listdir(output_folder):
        f_path = os.path.join(output_folder, f)
        if os.path.isfile(f_path):
            os.remove(f_path)
else:
    os.makedirs(output_folder)

# Step 2: Get list of .dxf files in QA folder
files = [f for f in os.listdir(folder_qa) if f.lower().endswith('.dxf')]

# Step 3: Normalize function
def normalize_dxf(file_path):
    ignore_keywords = [
        '$timestart', '$timeend', '$lastsave', 'acadsignature',
        'createdate', 'modifydate', 'plotdate', 'savedby'
    ]
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = [line.strip().lower() for line in f if line.strip()]
    entities = []
    current_entity = []
    i = 0
    while i < len(lines):
        group_code = lines[i]
        value = lines[i + 1] if i + 1 < len(lines) else ""
        if group_code == '0' and current_entity:
            entities.append(current_entity)
            current_entity = []
        if not any(kw in value for kw in ignore_keywords):
            value = re.sub(
                r'([-+]?[0-9]*\.?[0-9]+)',
                lambda m: f"{float(m.group()):.6f}",
                value
            )
            current_entity.append(f"{group_code} {value}")
        i += 2
    if current_entity:
        entities.append(current_entity)
    normalized_entities = sorted(['\n'.join(e) for e in entities])
    return normalized_entities

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


# Step 5: Compare and collect differences
different_files = []

for filename in files:
    qa_path = os.path.join(folder_qa, filename)
    prd_path = os.path.join(folder_prd, filename)

    if os.path.isfile(prd_path):
        content_qa = normalize_dxf(qa_path)
        content_prd = normalize_dxf(prd_path)

        if content_qa == content_prd:
            print(f"✅ File {filename} is the same")
        else:
            print(f"❌ File {filename} is different")
            name, ext = os.path.splitext(filename)
            shutil.copy2(qa_path, os.path.join(output_folder, f"{name}_qa{ext}"))
            shutil.copy2(prd_path, os.path.join(output_folder, f"{name}_prd{ext}"))
            different_files.append(filename)
    else:
        print(f"⚠️ File {filename} not found in PRD folder, skipping.")

# Step 6: Visualize the differences
for filename in different_files:
    qa_path = os.path.join(folder_qa, filename)
    prd_path = os.path.join(folder_prd, filename)
    print(f"\n🔍 Showing visual diff for {filename}")
    overlay_dxf(qa_path, prd_path, filename)
