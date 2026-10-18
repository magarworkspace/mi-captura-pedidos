import streamlit as st
import pandas as pd
import io
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

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

# ==============================================================================
# ⚠️ CONFIGURACIÓN DE TU CORREO (DEJA LAS COMILLAS Y CAMBIA SOLO LO DE ADENTRO)
# ==============================================================================
EMAIL_EMISOR = "magarworkspace@gmail.com" 
PASSWORD_EMISOR = "f6ZbKU.cPJurM5f"  # Pon tus 16 letras pegadas y sin espacios
# ==============================================================================

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

# Función corregida con puerto SSL 465 directo para evitar el error -2
def enviar_correo_con_adjunto(correo_destino, archivo_bytes):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_EMISOR
        msg['To'] = correo_destino
        msg['Subject'] = "Nuevo Pedido Semanal de Refacciones"
        
        cuerpo = "Hola, adjunto el archivo generado con el pedido de esta semana. Saludos."
        msg.attach(MIMEText(cuerpo, 'plain'))
        
        adjunto = MIMEBase('application', 'octet-stream')
        adjunto.set_payload(archivo_bytes)
        encoders.encode_base64(adjunto)
        adjunto.add_header('Content-Disposition', 'attachment; filename="Pedido_Semanal.xlsx"')
        msg.attach(adjunto)
        
        # Conexión ultra segura directa al servidor de Gmail (Puerto 465)
        server = smtplib.SMTP_SSL('://gmail.com', 465)
        server.login(EMAIL_EMISOR, PASSWORD_EMISOR)
        text = msg.as_string()
        server.sendmail(EMAIL_EMISOR, correo_destino, text)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Error al enviar el correo: {str(e)}")
        return False

# 1. Carga del Archivo
st.subheader("📂 1. Arrastra aquí el Excel o CSV del proveedor")
archivo_cargado = st.file_uploader("", type=["xlsx", "csv"], label_visibility="collapsed")

if archivo_cargado:
    try:
        df_base = cargar_datos(archivo_cargado)
        
        # 2. Entrada de Presupuesto
        st.subheader("💰 Ingresa el Presupuesto Semanal:")
        presupuesto = st.number_input("", min_value=0.0, value=50000.0, step=1000.0, label_visibility="collapsed")

        # 3. Módulo de Escaneo Inteligente
        st.subheader("🔍 Escanear Código de Barras (Clave)")
        
        def procesar_escaneo():
            st.session_state.codigo_a_procesar = st.session_state.scanner_input.strip()
            st.session_state.scanner_input = ""

        st.text_input("Haz clic aquí antes de usar tu escáner/cámara", key="scanner_input", on_change=procesar_escaneo)

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
                st.session_state.codigo_a_procesar = ""

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
                if st.button("✉️ Enviar Pedido por E-mail"):
                    st.session_state.abrir_email = True
                    
                if st.session_state.get("abrir_email", False):
                    correo_destino = st.text_input("Ingresa el correo del destinatario:")
                    if st.button("Confirmar Envío"):
                        output = io.BytesIO()
                        df_final = df_base.copy()
                        df_final['CANTIDAD'] = df_final['CLAVE PRODUCTO'].map(
                            lambda x: st.session_state.carrito[x.strip()]['cantidad'] if x.strip() in st.session_state.carrito else ""
                        )
                        
                        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                            df_final.to_excel(writer, index=False, sheet_name='Pedido')
                        
                        if enviar_correo_con_adjunto(correo_destino, output.getvalue()):
                            st.success(f"¡Pedido enviado con éxito a {correo_destino}!")
                        st.session_state.abrir_email = False

            with col2:
                if not st.session_state.confirmar_borrar:
                    if st.button("🧹 Clear"):
                        st.session_state.confirmar_borrar = True
                        st.rerun()
                else:
                    st.warning("⚠️ ¿Borrar todo el pedido?")
                    col_si, col_no = st.columns(2)
                    with col_si:
                        if st.button("SÍ, BORRAR", type="primary"):
                            st.session_state.carrito = {}
                            st.session_state.confirmar_borrar = False
                            st.toast("Pedido limpiado.")
                            st.rerun()
                    with col_no:
                        if st.button("Cancelar"):
                            st.session_state.confirmar_borrar = False
                            st.rerun()
        else:
            st.info("El carrito está vacío. Escanea productos arriba para empezar.")
            
    except Exception as e:
        st.error(f"Error interno: {str(e)}")
