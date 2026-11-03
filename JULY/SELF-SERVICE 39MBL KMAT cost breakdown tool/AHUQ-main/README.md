

# 🛠️ AHUQ Tool 

AHUQ is a desktop application designed to streamline engineering workflows by providing tools for:

* 🔍 DXF file comparison (geometry-based, no false positives)
* 🧪 xPloder rule testing
* 📄 XML query handling

The tool is built with Python and distributed as a standalone executable for easy use.

---

## 🚀 Features

### 🟦 DXF Compare (Main Feature)

* Compares DXF files **based on geometry**, not raw text
* Eliminates false positives caused by:

  * metadata differences
  * handles / IDs
  * timestamps
* Supports:

  * LINE, CIRCLE, ARC, POLYLINE, LWPOLYLINE, SPLINE, TEXT, INSERT, etc.
* Outputs:

  * ✅ Matches
  * ❌ Differences with entity counts
  * ⚠️ Missing files

### 🎯 Visual Difference Viewer

* Fullscreen grid of all differing DXF files
* Overlay visualization:

  * **Cyan → Folder PRD**
  * **Magenta → Folder QA**
* Easy visual detection of mismatches

### 🔎 Smart Filtering

* Filter results by filename
* Does not affect comparison, only display

---

### 🧪 xPloder Rule Test

* Batch test `.rule` files
* Input multiple part numbers
* Clipboard support

---

### 📄 XML Query Tool

* Query XML files quickly
* Structured output display

---

## 📦 Project Structure

```
AHUQ/
│
├── AHUQ_Mar2026.py      # Main application (source code)
│
├── dist/
│   └── AHUQ_Mar2026.exe # Standalone executable
│
├── README.md
```

---

## ▶️ How to Run

### Executable (Recommended)

No setup required.

```
dist/AHUQ_Mar2026.exe
```

---



## 🧠 How DXF Comparison Works

Instead of comparing raw DXF text, the tool:

1. Reads only **modelspace entities**
2. Extracts geometry:

   * coordinates
   * radii
   * angles
3. Normalizes values (precision control)
4. Compares entity sets

### Result:

✔ Accurate comparison
✔ No noise from metadata
✔ Meaningful differences only

---

## 📊 Output Interpretation

Example:

```
❌ part123.dxf | ΔA:0 ΔB:19
```

Meaning:

* Folder A is fully contained in Folder B
* Folder B has 19 extra entities

---

## 🎨 Visualization Logic

| Color   | Meaning       |
| ------- | ------------- |
| Cyan    | Folder PRD    |
| Magenta | Folder QA     |
| Overlap | Same geometry |

---

## ⚠️ Known Limitations

* Different representations of same geometry may still show differences:

  * polyline vs multiple lines
  * blocks vs exploded geometry
* Very large DXFs may take longer to render in grid view

---


