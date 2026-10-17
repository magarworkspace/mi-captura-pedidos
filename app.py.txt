import streamlit as st
import pandas as pd
import io

# Configuración de la página para dispositivos móviles y tema oscuro
st.set_page_config(page_title="Mi Captura de Pedidos", layout="centered")

# Estilos personalizados (CSS inyectado) para lograr el look de tu captura
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

# 1. Carga del Archivo (Optimizado para no saturar memoria)
st.subheader("📂 1. Arrastra aquí el Excel o CSV del proveedor")
archivo_cargado = st.file_uploader("", type=["xlsx", "csv"], label_visibility="collapsed")

# Inicializar estados de la aplicación
if "carrito" not in st.session_state:
    st.session_state.carrito = {}
if "confirmar_borrar" not in st.session_state:
    st.session_state.confirmar_borrar = False

if archivo_cargado:
    # Leer el archivo omitiendo las filas de encabezado basura de arriba
    @st.cache_data
    def cargar_datos(archivo):
        if archivo.name.endswith('.csv'):
            df = pd.read_csv(archivo, skiprows=10) # Ajusta según las filas vacías
        else:
            df = pd.read_excel(archivo, skiprows=10)
        # Limpiar espacios en los nombres de columnas
        df.columns = df.columns.str.strip()
        return df

    try:
        df_base = cargar_datos(archivo_cargado)
        
        # 2. Entrada de Presupuesto
        st.subheader("💰 Ingresa el Presupuesto Semanal Neto:")
        presupuesto = st.number_input("", min_value=0.0, value=50000.0, step=1000.0, label_visibility="collapsed")

        # 3. Módulo de Escaneo Simulado para Celular
        st.subheader("🔍 Escanear Código de Barras (Clave)")
        codigo_escaneado = st.text_input("Haz clic aquí antes de usar tu escáner/cámara", key="scanner").strip()

        if codigo_escaneado:
            # Buscar el producto por CLAVE PRODUCTO
            producto_match = df_base[df_base['CLAVE PRODUCTO'].str.strip() == codigo_escaneado]
            
            if not producto_match.empty:
                idx = producto_match.index[0]
                desc = producto_match.loc[idx, 'DESCRIPCION']
                precio_uni = float(producto_match.loc[idx, 'PRECIO UNITARIO'])
                
                st.success(f"Detectado: {desc}")
                
                # Pedir cantidad inmediatamente abajo del escaneo
                cant = st.number_input(f"Cantidad para {codigo_escaneado}:", min_value=1, value=1, step=1)
                
                if st.button("Agregar al Pedido"):
                    st.session_state.carrito[codigo_escaneado] = {
                        "descripcion": desc,
                        "precio_unitario": precio_uni,
                        "cantidad": cant
                    }
                    st.toast("¡Producto añadido!")
            else:
                st.error("Código no encontrado en la lista de precios.")

        # 4. Cálculos y Resumen del Pedido
        st.subheader("📊 Resumen del Pedido")
        
        if st.session_state.carrito:
            # Calcular Suma de Netos (Equivalente a tu celda K8)
            suma_netos = sum(item["precio_unitario"] * item["cantidad"] for item in st.session_state.carrito.values())
            
            # Aplicar tu Fórmula Matemática Comercial Exacta (Neto + IVA 16% - Descuento 22.13%)
            monto_final_real = (suma_netos * 1.16) * (1 - 0.2213)
            
            # Renderizado del Semáforo Visual
            if monto_final_real <= presupuesto:
                clase_semaforo = "verde"
                mensaje_semaforo = f"🟢 DENTRO DEL PRESUPUESTO (Total Real: ${monto_final_real:,.2f} MXN)"
            else:
                clase_semaforo = "rojo"
                mensaje_semaforo = f"🔴 PRESUPUESTO SUPERADO (Total Real: ${monto_final_real:,.2f} MXN)"
                
            st.markdown(f'<div class="metric-box {clase_semaforo}"><h3>{mensaje_semaforo}</h3></div>', unsafe_allow_html=True)
            
            # Mostrar Tabla de lo acumulado
            df_carrito = pd.DataFrame.from_dict(st.session_state.carrito, orient='index')
            st.dataframe(df_carrito[['descripcion', 'cantidad', 'precio_unitario']], use_container_width=True)

            # --- SECCIÓN DE BOTONES DE ACCIÓN ---
            col1, col2 = st.columns(2)
            
            with col1:
                # Botón de Email Abierto
                if st.button("✉️ Enviar Pedido por E-mail"):
                    st.session_state.abrir_email = True
                    
                if st.session_state.get("abrir_email", False):
                    correo_destino = st.text_input("Ingresa el correo del destinatario:")
                    if st.button("Confirmar Envío"):
                        # Aquí procesamos el archivo final en memoria
                        output = io.BytesIO()
                        # Volvemos a mapear los datos originales agregando las cantidades capturadas
                        df_final = df_base.copy()
                        df_final['CANTIDAD'] = df_final['CLAVE PRODUCTO'].map(
                            lambda x: st.session_state.carrito[x.strip()]['cantidad'] if x.strip() in st.session_state.carrito else ""
                        )
                        
                        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                            df_final.to_excel(writer, index=False, sheet_name='Pedido')
                        
                        # Simulación de envío exitoso (puedes conectar una API como SendGrid o SMTP de Gmail aquí)
                        st.success(f"¡Pedido enviado exitosamente a {correo_destino}!")
                        st.session_state.abrir_email = False

            with col2:
                # Botón Clear con Doble Confirmación Corta
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
        st.error("Error al procesar el archivo. Asegúrate de que las columnas coincidan con el formato original.")
