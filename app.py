import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import io

# Configuración de la página web
st.set_page_config(page_title="Generador de Reportes Etelix", page_icon="📊", layout="centered")

st.title("📊 Generador de Reportes Etelix")
st.markdown("Sube el archivo consolidado del OCOM (.csv). El archivo de series CRC ya está cargado en el sistema.")

# Diccionario Oficial de Códigos SIP
descripciones_sip = {
    '100': '100 Intentando', '180': '180 Timbrando', '183': '183 Progreso de la Sesión',
    '200': '200 OK (Éxito)', '400': '400 Solicitud Errónea', '401': '401 No Autorizado',
    '403': '403 Prohibido', '404': '404 No Encontrado', '408': '408 Expiración',
    '480': '480 Temporalmente No Disponible', '486': '486 Ocupado Aquí', 
    '487': '487 Solicitud Terminada', '488': '488 No Aceptable Aquí',
    '500': '500 Error Interno', '502': '502 Gateway Inválido', '503': '503 Servicio No Disponible',
    '603': '603 Rechazo'
}

# 1. ARCHIVO DE SERIES FIJO (Debe estar en la misma carpeta que este script en el servidor)
ruta_series = "Series por operador.csv"

# 2. CARGADOR DE ARCHIVO PARA EL USUARIO
archivo_ocom = st.file_uploader("Sube el consolidado del OCOM (.csv)", type=['csv'])

if archivo_ocom is not None:
    if st.button("Generar Reporte"):
        with st.spinner("Procesando datos y generando gráficas..."):
            try:
                # Lectura de datos
                df = pd.read_csv(archivo_ocom, sep=',', low_memory=False)
                df_series = pd.read_csv(ruta_series, sep=',') 
                df_series.columns = df_series.columns.str.strip()
                
                if 'code' in df.columns:
                    df = df[df['code'] != 'code']
                    
                df['dst_user_clean'] = df['dst_user'].astype(str).str.replace('^20000257', '', regex=True)
                df['dst_user_num'] = pd.to_numeric(df['dst_user_clean'], errors='coerce')

                df_series['N1'] = pd.to_numeric(df_series['N1'], errors='coerce')
                df_series['N2'] = pd.to_numeric(df_series['N2'], errors='coerce')
                df_series = df_series.dropna(subset=['N1', 'N2', 'OPERADOR'])
                
                df_series = df_series.sort_values('N1')
                df_valido = df.dropna(subset=['dst_user_num']).sort_values('dst_user_num')

                df_series['N1'] = df_series['N1'].astype('int64')
                df_series['N2'] = df_series['N2'].astype('int64')
                df_valido['dst_user_num'] = df_valido['dst_user_num'].astype('int64')

                df_merged = pd.merge_asof(
                    df_valido, df_series[['N1', 'N2', 'OPERADOR']], 
                    left_on='dst_user_num', right_on='N1', direction='backward'
                )

                df_merged['Operador_Final'] = np.where(
                    df_merged['dst_user_num'] <= df_merged['N2'],
                    df_merged['OPERADOR'], 'Desconocido / Fuera de Rango'
                )
                df_merged['Operador_Final'] = df_merged['Operador_Final'].replace('', 'Desconocido / Fuera de Rango')
                
                resumen_operadores = df_merged['Operador_Final'].value_counts()
                resumen_codigos = df_merged['code'].value_counts()

                def agrupar_centena(cod):
                    cod_str = str(cod)
                    if cod_str.startswith('1'): return '1XX (Informativas)'
                    if cod_str.startswith('2'): return '2XX (Éxitos)'
                    if cod_str.startswith('3'): return '3XX (Redirección)'
                    if cod_str.startswith('4'): return '4XX (Errores de Cliente)'
                    if cod_str.startswith('5'): return '5XX (Errores de Red/Servidor)'
                    if cod_str.startswith('6'): return '6XX (Fallas Globales)'
                    return 'Otros'

                df_merged['Familia_SIP'] = df_merged['code'].apply(agrupar_centena)
                resumen_familias = df_merged['Familia_SIP'].value_counts()

                plt.style.use('ggplot') 
                def color_codigo(cod):
                    cod_str = str(cod)
                    if cod_str.startswith('1'): return '#17becf' 
                    if cod_str.startswith('2'): return '#2ca02c' 
                    if cod_str.startswith('3'): return '#bcbd22' 
                    if cod_str.startswith('4'): return '#ff7f0e' 
                    if cod_str.startswith('5') or cod_str.startswith('6'): return '#d62728' 
                    return '#7f7f7f'

                # Crear gráficas en memoria RAM (BytesIO)
                img_operadores = io.BytesIO()
                plt.figure(figsize=(10, 6))
                colores_barras = plt.cm.viridis(np.linspace(0.2, 0.9, len(resumen_operadores)))
                resumen_operadores.plot(kind='bar', color=colores_barras, edgecolor='black', linewidth=0.5)
                plt.title('Tráfico por Operador Destino', fontsize=15, fontweight='bold', pad=15)
                plt.xticks(rotation=35, ha='right')
                plt.tight_layout()
                plt.savefig(img_operadores, format='png', dpi=300)
                plt.close()

                img_barras = io.BytesIO()
                plt.figure(figsize=(10, 6))
                colores_codigos = [color_codigo(cod) for cod in resumen_codigos.index]
                resumen_codigos.plot(kind='bar', color=colores_codigos, edgecolor='black', linewidth=0.5)
                plt.title('Volumen por Código SIP', fontsize=15, fontweight='bold', pad=15)
                plt.xticks(rotation=0)
                plt.tight_layout()
                plt.savefig(img_barras, format='png', dpi=300)
                plt.close()

                img_torta = io.BytesIO()
                plt.figure(figsize=(10, 7))
                colores_familias = [color_codigo(fam[:1]) for fam in resumen_familias.index]
                separacion = [0.05] * len(resumen_familias)
                wedges, texts, autotexts = plt.pie(
                    resumen_familias, autopct=lambda pct: ('%1.1f%%' % pct) if pct > 3 else '', 
                    startangle=140, colors=colores_familias, shadow=True, explode=separacion,
                    wedgeprops={'edgecolor': 'black', 'linewidth': 1}
                )
                etiquetas = [f"{fam} ({cant:,})" for fam, cant in zip(resumen_familias.index, resumen_familias)]
                plt.legend(wedges, etiquetas, title="Familias SIP", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
                plt.title('Proporción de Códigos', fontsize=15, fontweight='bold', pad=20)
                plt.tight_layout()
                plt.savefig(img_torta, format='png', dpi=300)
                plt.close()

                # Consolidación del Excel en memoria RAM
                output = io.BytesIO()
                writer = pd.ExcelWriter(output, engine='xlsxwriter')
                
                df_export = pd.DataFrame({'Operador_CRC': resumen_operadores.index, 'Cantidad': resumen_operadores.values})
                df_export_codigos = pd.DataFrame({'Código_SIP': resumen_codigos.index, 'Cantidad': resumen_codigos.values})
                df_export_codigos['Descripción'] = df_export_codigos['Código_SIP'].astype(str).map(descripciones_sip).fillna('Código no especificado')
                df_export_codigos = df_export_codigos[['Código_SIP', 'Descripción', 'Cantidad']]
                df_export_familias = pd.DataFrame({'Familia_SIP': resumen_familias.index, 'Cantidad': resumen_familias.values})

                df_export.to_excel(writer, sheet_name='Operadores', index=False)
                df_export_codigos.to_excel(writer, sheet_name='Códigos Detallados', index=False)
                df_export_familias.to_excel(writer, sheet_name='Códigos Agrupados', index=False)
                
                ws_operadores = writer.sheets['Operadores']
                ws_codigos_det = writer.sheets['Códigos Detallados']
                ws_codigos_fam = writer.sheets['Códigos Agrupados']
                
                ws_operadores.set_column('A:B', 35)
                ws_codigos_det.set_column('A:A', 15)
                ws_codigos_det.set_column('B:B', 45)
                ws_codigos_det.set_column('C:C', 15)
                ws_codigos_fam.set_column('A:B', 35)
                
                ws_operadores.insert_image('D2', '1_Operadores.png', {'image_data': img_operadores, 'x_scale': 0.65, 'y_scale': 0.65})
                ws_codigos_det.insert_image('E2', '2_Codigos_Barras.png', {'image_data': img_barras, 'x_scale': 0.65, 'y_scale': 0.65})
                ws_codigos_fam.insert_image('D2', '3_Codigos_Torta.png', {'image_data': img_torta, 'x_scale': 0.65, 'y_scale': 0.65})
                
                writer.close()
                excel_data = output.getvalue()

                st.success("✅ ¡Reporte generado con éxito!")
                
                # Botón de descarga para el usuario
                nombre_archivo_salida = archivo_ocom.name.replace('consolidado_etelix', 'Reporte_Etelix_Final').replace('.csv', '.xlsx')
                st.download_button(
                    label="📥 Descargar Reporte en Excel",
                    data=excel_data,
                    file_name=nombre_archivo_salida,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            except Exception as e:
                st.error(f"❌ Ocurrió un error inesperado: {e}")