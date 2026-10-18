import streamlit as st
import pandas as pd
import io
import urllib.parse
import streamlit.components.v1 as components

st.set_page_config(page_title="Mi Captura de Pedidos", layout="centered")

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

if "carrito" not in st.session_state:
    st.session_state.carrito = {}
if "confirmar_borrar" not in st.session_state:
    st.session_state.confirmar_borrar = False

query_params = st.query_params
if "code_scanned" in query_params:
    st.session_state.codigo_a_procesar = query_params["code_scanned"]
    st.query_params.clear()

if "codigo_a_procesar" not in st.session_state:
    st.session_state.codigo_a_procesar = ""

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

archivo_cargado = st.file_uploader("", type=["xlsx", "csv"], label_visibility="collapsed")
if archivo_cargado:
    try:
        df_base = cargar_datos(archivo_cargado)
        presupuesto = st.number_input("💰 Presupuesto Semanal:", min_value=0.0, value=50000.0, step=1000.0)
        
        scanner_manual = st.text_input("Escribe el código manualmente:", key="manual_input").strip()
        if scanner_manual:
            st.session_state.codigo_a_procesar = scanner_manual

        st.markdown("---")
        st.write("📷 Enfoca el código de barras:")
        
        escaner_js = """
        <div id="interactive" class="viewport" style="width: 100%; max-width: 480px; height: 260px; position: relative; background: #161b22; border-radius: 10px; overflow: hidden; margin: 0 auto;">
            <video autoplay playsinline style="width: 100%; height: 100%; object-fit: cover;"></video>
            <div style="position: absolute; top: 50%; left: 5%; width: 90%; height: 2px; background: red; opacity: 0.7; transform: translateY(-50%); box-shadow: 0 0 4px red;"></div>
        </div>
        <script src="https://cloudflare.com"></script>
        <script>
            Quagga.init({
                inputStream : { name : "Live", type : "LiveStream", target: document.querySelector('#interactive'), constraints: { width: 640, height: 480, facingMode: "environment" } },
                decoder : { readers : ["code_128_reader", "ean_reader", "ean_8_reader", "code_39_reader"] }
            }, function(err) { if (!err) Quagga.start(); });
            Quagga.onDetected(function(data) {
                const code = data.codeResult.code;
                if (code) {
                    const url = new URL(window.parent.location.href);
                    url.searchParams.set("code_scanned", code);
                    window.parent.location.href = url.href;
                    Quagga.stop();
                }
            });
        </script>
        """
        components.html(escaner_js, height=290)

        if st.session_state.codigo_a_procesar:
            codigo = st.session_state.codigo_a_procesar
            producto_match = df_base[df_base['CLAVE PRODUCTO'].str.strip() == codigo]
            if not producto_match.empty:
                idx = producto_match.index
                desc = producto_match.loc[idx, 'DESCRIPCION'].values[0]
                precio_uni = float(producto_match.loc[idx, 'PRECIO UNITARIO'].values[0])
                st.success(f"Detectado: {desc}")
                with st.form(key="form_agregar"):
                    cant = st.number_input(f"Cantidad para {codigo}:", min_value=1, value=1, step=1)
                    if st.form_submit_button("Confirmar y Agregar"):
                        st.session_state.carrito[codigo] = {"descripcion": desc, "precio_unitario": precio_uni, "cantidad": cant}
                        st.session_state.codigo_a_procesar = ""
                        st.rerun()
            else:
                st.error(f"Código '{codigo}' no encontrado.")
                if st.button("Limpiar"):
                    st.session_state.codigo_a_procesar = ""
                    st.rerun()

        if st.session_state.carrito:
            suma_netos = sum(item["precio_unitario"] * item["cantidad"] for item in st.session_state.carrito.values())
            monto_final_real = (suma_netos * 1.16) * (1 - 0.2213)
            clase_s = "verde" if monto_final_real <= presupuesto else "rojo"
            msg_s = f"🟢 Total: ${monto_final_real:,.2f}" if monto_final_real <= presupuesto else f"🔴 Superado: ${monto_final_real:,.2f}"
            st.markdown(f'<div class="metric-box {clase_s}"><h3>{msg_s}</h3></div>', unsafe_allow_html=True)
            
            df_carrito = pd.DataFrame.from_dict(st.session_state.carrito, orient='index')
            st.dataframe(df_carrito[['descripcion', 'cantidad', 'precio_unitario']], use_container_width=True)

            col1, col2 = st.columns(2)
            with col1:
                output = io.BytesIO()
                df_final = df_base.copy()
                df_final['CANTIDAD'] = df_final['CLAVE PRODUCTO'].map(lambda x: st.session_state.carrito[x.strip()]['cantidad'] if x.strip() in st.session_state.carrito else "")
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_final.to_excel(writer, index=False, sheet_name='Pedido')
                st.download_button(label="📥 Guardar Excel", data=output.getvalue(), file_name="Pedido.xlsx", use_container_width=True)

            with col2:
                if not st.session_state.confirmar_borrar:
                    if st.button("🧹 Clear", use_container_width=True):
                        st.session_state.confirmar_borrar = True
                        st.rerun()
                else:
                    st.warning("⚠️ ¿Borrar?")
                    if st.button("SÍ", type="primary"):
                        st.session_state.carrito = {}
                        st.session_state.confirmar_borrar = False
                        st.rerun()
                    if st.button("NO"):
                        st.session_state.confirmar_borrar = False
                        st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")
