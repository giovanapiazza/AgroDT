import streamlit as st
import opcua_bridge # Importa nossa nova ponte

st.set_page_config(page_title="AgroDT Control", layout="wide")

st.title("🤖 AgroDT - Painel de Controle")

# Seção de Telemetria (OPC-UA)
st.subheader("📡 Telemetria do Drone (via OPC-UA)")

# Configurações de conexão
url_opc = st.text_input("URL do Servidor OPC-UA", "opc.tcp://localhost:4840/freeopcua/server/")
node_id_opc = st.text_input("Node ID (Ex: ns=2;i=2)", "ns=2;i=2")

if st.button("Atualizar Telemetria"):
    with st.spinner("Conectando ao drone..."):
        # Chama a função da ponte, que já resolve o async
        valor = opcua_bridge.ler_sensor_opcua(url_opc, node_id_opc)
        st.success(f"Dado recebido: {valor}")

st.divider()

# Seção de Tradutor de Código (Seu código anterior)
st.subheader("🛠️ Tradutor de Código")
# ... (seu código do tradutor aqui)
