import streamlit as st
import pandas as pd
import io
import urllib.parse
import streamlit.components.v1 as components

# Configuración de la página para dispositivos móviles y tema oscuro
st.set_page_config(page_title="Mi Captura de Pedidos", layout="centered")

# Estilos personalizados (CSS inyectado)
st.markdown("""
    <style>
    .main { background-color: #0d1117; }
    h1, h2, h3 { color: #ffffff; }
    .stNumberInput div div input { background-color: #161b22; color: white; }
    .metric-box { padding: 15px; border-radius: 8px; margin-bottom: 15px; font-weight: bold; text-align: center; }
    .verde { background-color: #1b4332; color: #75e6da; border: 1px solid #2d6a4f; }
    .rojo { background-color: #660708; color: #ffb3c1; border: 1px solid #a4161a; }
    </style>
""", unsafe_allow_html=True)

st.title("📱 Mi Captura de Pedidos")

# Inicializar estados de la aplicación
if "carrito" not in st.session_state:
    st.session_state.carrito = {}
if "confirmar_borrar" not in st.session_state:
    st.session_state.confirmar_borrar = False
if "codigo_a_procesar" not in st.session_state:
    st.session_state.codigo_a_procesar = ""

# Función inteligente para buscar la fila de encabezados
@st.cache_data
def cargar_datos(archivo):
    if archivo.name.endswith('.csv'):
        df_crudo = pd.read_csv(archivo, header=None)
    else:
        df_crudo = pd.read_excel(archivo, header=None)
    
    fila_encabezado = 0
    for i, row in df_crudo.iterrows():
        valores_fila = [str(val).strip().upper() for val in row.values]
        if 'CLAVE PRODUCTO' in valores_fila or 'ID PRODUCTO' in valores_fila:
            fila_encabezado = i
            break
    
    archivo.seek(0)
    if archivo.name.endswith('.csv'):
        df = pd.read_csv(archivo, skiprows=fila_encabezado)
    else:
        df = pd.read_excel(archivo, skiprows=fila_encabezado)
        
    df.columns = df.columns.str.strip()
    return df

# 1. Carga del Archivo
st.subheader("📂 1. Arrastra aquí el Excel o CSV del proveedor")
archivo_cargado = st.file_uploader("", type=["xlsx", "csv"], label_visibility="collapsed")

if archivo_cargado:
    try:
        df_base = cargar_datos(archivo_cargado)
        
        # 2. Entrada de Presupuesto
        st.subheader("💰 Ingresa el Presupuesto Semanal:")
        presupuesto = st.number_input("", min_value=0.0, value=50000.0, step=1000.0, label_visibility="collapsed")

        # 3. Módulo de Escaneo con Cámara Integrada
        st.subheader("🔍 Módulo de Escaneo")
        
        # Opción A: Escaneo Manual con Teclado
        scanner_manual = st.text_input("Escribe el código manualmente si lo prefieres:", key="manual_input").strip()
        if scanner_manual:
            st.session_state.codigo_a_procesar = scanner_manual

        # Opción B: Escáner de Video HTML5 Nativo (Cámara Trasera)
        st.markdown("---")
        st.write("📷 Video continuo con cámara trasera activa:")
        
        # Inyección de la cámara nativa mediante JavaScript para evitar congelamientos
        componente_html = """
        <div style="text-align: center;">
            <video id="video" width="100%" height="auto" style="border-radius: 10px; background-color: #161b22;" autoplay playsinline></video>
            <p style="color: #8b949e; font-size: 14px; margin-top: 8px;">Apunta al texto o código de la refacción</p>
        </div>
        <script>
            const video = document.getElementById('video');
            // Forzamos nativamente el uso de la cámara trasera ('environment') y video continuo fluido
            const constraints = {
                video: { facingMode: { exact: "environment" } }
            };

            navigator.mediaDevices.getUserMedia(constraints)
                .then((stream) => {
                    video.srcObject = stream;
                })
                .catch((err) => {
                    // Si falla el modo exacto (por ejemplo en PC), usamos cualquier cámara trasera disponible
                    navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
                        .then((stream) => { video.srcObject = stream; })
                        .catch((e) => console.error("Error al abrir cámara: ", e));
                });
        </script>
        """
        # Desplegamos el visor nativo en la app móvil
        components.html(componente_html, height=280)

        # Procesamiento del código obtenido
        if st.session_state.codigo_a_procesar:
            codigo = st.session_state.codigo_a_procesar
            producto_match = df_base[df_base['CLAVE PRODUCTO'].str.strip() == codigo]
            
            if not producto_match.empty:
                idx = producto_match.index
                desc = producto_match.loc[idx, 'DESCRIPCION'].values
                precio_uni = float(producto_match.loc[idx, 'PRECIO UNITARIO'].values)
                
                st.success(f"Detectado: {desc}")
                
                with st.form(key="form_agregar"):
                    cant = st.number_input(f"Cantidad para {codigo}:", min_value=1, value=1, step=1)
                    boton_confirmar = st.form_submit_button("Confirmar y Agregar")
                    
                    if boton_confirmar:
                        st.session_state.carrito[codigo] = {
                            "descripcion": desc,
                            "precio_unitario": precio_uni,
                            "cantidad": cant
                        }
                        st.session_state.codigo_a_procesar = ""
                        st.toast("¡Producto añadido!")
                        st.rerun()
            else:
                st.error(f"Código '{codigo}' no encontrado en la lista de precios.")
                if st.button("Limpiar y volver a escanear"):
                    st.session_state.codigo_a_procesar = ""
                    st.rerun()

        # 4. Cálculos y Resumen del Pedido
        st.subheader("📊 Resumen del Pedido")
        
        if st.session_state.carrito:
            suma_netos = sum(item["precio_unitario"] * item["cantidad"] for item in st.session_state.carrito.values())
            monto_final_real = (suma_netos * 1.16) * (1 - 0.2213)
            
            if monto_final_real <= presupuesto:
                clase_semaforo = "verde"
                mensaje_semaforo = f"🟢 DENTRO DEL PRESUPUESTO (Total Real: ${monto_final_real:,.2f} MXN)"
            else:
                clase_semaforo = "rojo"
                mensaje_semaforo = f"🔴 PRESUPUESTO SUPERADO (Total Real: ${monto_final_real:,.2f} MXN)"
                
            st.markdown(f'<div class="metric-box {clase_semaforo}"><h3>{mensaje_semaforo}</h3></div>', unsafe_allow_html=True)
            
            df_carrito = pd.DataFrame.from_dict(st.session_state.carrito, orient='index')
            st.dataframe(df_carrito[['descripcion', 'cantidad', 'precio_unitario']], use_container_width=True)

            # --- SECCIÓN DE BOTONES DE ACCIÓN ---
            col1, col2 = st.columns(2)
            
            with col1:
                output = io.BytesIO()
                df_final = df_base.copy()
                df_final['CANTIDAD'] = df_final['CLAVE PRODUCTO'].map(
                    lambda x: st.session_state.carrito[x.strip()]['cantidad'] if x.strip() in st.session_state.carrito else ""
                )
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_final.to_excel(writer, index=False, sheet_name='Pedido')
                excel_data = output.getvalue()

                st.download_button(
                    label="📥 Guardar Archivo Excel",
                    data=excel_data,
                    file_name="Pedido_Semanal.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                
                asunto = urllib.parse.quote("Nuevo Pedido Semanal de Refacciones")
                cuerpo = urllib.parse.quote("Hola, te comparto el pedido semanal. Adjunto el archivo generado por la app.")
                mailto_link = f"mailto:?subject={asunto}&body={cuerpo}"
                
                st.markdown(f'<a href="{mailto_link}" target="_blank"><button style="width:100%; padding:10px; background-color:#21262d; color:white; border:1px solid #30363d; border-radius:5px; font-weight:bold; cursor:pointer;">✉️ Redactar Correo</button></a>', unsafe_allow_html=True)

            with col2:
                if not st.session_state.confirmar_borrar:
                    if st.button("🧹 Clear", use_container_width=True):
                        st.session_state.confirmar_borrar = True
                        st.rerun()
                else:
                    st.warning("⚠️ ¿Borrar todo el pedido?")
                    col_si, col_no = st.columns(2)
                    with col_si:
                        if st.button("SÍ, BORRAR", type="primary", use_container_width=True):
                            st.session_state.carrito = {}
                            st.session_state.confirmar_borrar = False
                            st.rerun()
                    with col_no:
                        if st.button("NO, CANCELAR", use_container_width=True):
                            st.session_state.confirmar_borrar = False
                            st.rerun()
    except Exception as e:
        st.error(f"Error al procesar el archivo o la información: {e}")
