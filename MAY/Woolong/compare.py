from openpyxl import load_workbook, Workbook
from openpyxl.styles import PatternFill

# === CONFIGURACIÓN ===
archivo_excel = "1.xlsm"   # Cambia por tu archivo
hoja_1 = "Data_FE_Copeland"                 # Nombre de la primera hoja
hoja_2 = "Data_FE_LG"                 # Nombre de la segunda hoja
salida = "comparacion_diferencias.xlsx"

# === COLORES ===
rojo = PatternFill(start_color="FF9999", end_color="FF9999", fill_type="solid")
amarillo = PatternFill(start_color="FFFF99", end_color="FFFF99", fill_type="solid")

# === CARGAR ARCHIVO ===
wb = load_workbook(archivo_excel, data_only=True)
ws1 = wb[hoja_1]
ws2 = wb[hoja_2]

# === CREAR ARCHIVO DE RESULTADO ===
resultado = Workbook()
res = resultado.active
res.title = "Diferencias"

max_filas = max(ws1.max_row, ws2.max_row)
max_columnas = max(ws1.max_column, ws2.max_column)

# Encabezados
res.append(["Celda", "Valor Hoja 1", "Valor Hoja 2", "Resultado"])

# === COMPARACIÓN CELDA POR CELDA ===
for fila in range(1, max_filas + 1):
    for col in range(1, max_columnas + 1):
        valor1 = ws1.cell(row=fila, column=col).value
        valor2 = ws2.cell(row=fila, column=col).value

        if valor1 != valor2:
            celda = ws1.cell(row=fila, column=col).coordinate

            res.append([
                celda,
                valor1,
                valor2,
                "Diferente"
            ])

            # Resaltar diferencia en el reporte
            ultima_fila = res.max_row
            for c in range(1, 5):
                res.cell(row=ultima_fila, column=c).fill = amarillo

# === AJUSTAR ANCHO DE COLUMNAS ===
for columna in res.columns:
    max_largo = 0
    letra = columna[0].column_letter

    for celda in columna:
        if celda.value:
            max_largo = max(max_largo, len(str(celda.value)))

    res.column_dimensions[letra].width = max_largo + 3

# === GUARDAR RESULTADO ===
resultado.save(salida)

print(f"Comparación terminada. Archivo generado: {salida}")