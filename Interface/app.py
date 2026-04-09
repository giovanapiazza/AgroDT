import streamlit as st
import yaml
import json

# --- CONFIGURAÇÃO DE ESTILO ---
st.markdown("""
    <style>
    .stButton>button { background-color: #28a745; color: white; } /* Tudo clicável em verde */
    .used-prop { color: #856404; background-color: #fff3cd; padding: 2px 5px; border-radius: 3px; }
    .search-highlight { background-color: #d4edda; border-left: 5px solid #28a745; }
    </style>
    """, unsafe_allow_html=True)

# --- INICIALIZAÇÃO DO ESTADO ---
if 'project' not in st.session_state:
    st.session_state.project = {
        'aas_data': None,
        'protocols': {}, # { "MQTT": {"config": {}, "mappings": []} }
        'used_properties': set()
    }
if 'search_term' not in st.session_state:
    st.session_state.search_term = ""

# --- FUNÇÕES DE AUXÍLIO ---
def save_project():
    project_data = json.dumps({
        'aas_data': st.session_state.project['aas_data'],
        'protocols': st.session_state.project['protocols'],
        'used_properties': list(st.session_state.project['used_properties'])
    })
    st.download_button("Baixar Projeto (.json)", project_data, "projeto_tradutor.json")

def load_project(file):
    data = json.load(file)
    st.session_state.project['aas_data'] = data['aas_data']
    st.session_state.project['protocols'] = data['protocols']
    st.session_state.project['used_properties'] = set(data['used_properties'])

# --- SIDEBAR: PASSO 1 E GERAL ---
with st.sidebar:
    st.header("⚙️ Configuração")
    
    # Carregar AAS
    aas_file = st.file_uploader("Passo 1: Carregar AAS (JSON)", type=['json'])
    if aas_file:
        st.session_state.project['aas_data'] = json.load(aas_file)
    
    # Carregar Projeto Existente
    uploaded_proj = st.file_uploader("Carregar Projeto Existente", type=['json'])
    if uploaded_proj:
        load_project(uploaded_proj)

    # Passo 2: Definir Protocolos
    num_protocols = st.number_input("Passo 2: Quantos protocolos?", min_value=0, value=len(st.session_state.project['protocols']))
    for i in range(num_protocols):
        p_name = st.text_input(f"Nome do Protocolo {i+1}", key=f"pname_{i}")
        if p_name and p_name not in st.session_state.project['protocols']:
            st.session_state.project['protocols'][p_name] = {"config": "", "mappings": []}

    if st.button("💾 Salvar Progresso"):
        save_project()

# --- ÁREA PRINCIPAL ---
st.title("AAS Protocol Translator")

if st.session_state.project['aas_data']:
    # Busca na AAS Tree
    st.session_state.search_term = st.text_input("🔍 Buscar na AAS Tree", help="Destaca onde o dado está")

    # Layout: Coluna 1 (Mappings/Abas) | Coluna 2 (AAS Tree)
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Passo 3 & 4: Protocolos")
        tabs = st.tabs(list(st.session_state.project['protocols'].keys())) if st.session_state.project['protocols'] else []

        for idx, tab in enumerate(tabs):
            p_name = list(st.session_state.project['protocols'].keys())[idx]
            with tab:
                # Configuração Geral
                st.session_state.project['protocols'][p_name]['config'] = st.text_area(f"Configuração {p_name}", 
                                                                                     value=st.session_state.project['protocols'][p_name]['config'])
                
                # Gerenciar Mappings
                st.write("---")
                st.write("**Mappings**")
                
                # Adicionar nova linha de mapping
                if st.button(f"➕ Adicionar Linha em {p_name}", key=f"add_{p_name}"):
                    st.session_state.project['protocols'][p_name]['mappings'].append({"origin": "", "dest": ""})

                # Listar Mappings Existentes
                for m_idx, mapping in enumerate(st.session_state.project['protocols'][p_name]['mappings']):
                    c_orig, c_dest, c_del = st.columns([2, 2, 1])
                    
                    with c_orig:
                        mapping['origin'] = st.text_input("Origem", value=mapping['origin'], key=f"orig_{p_name}_{m_idx}")
                    
                    with c_dest:
                        # Passo 5: Selecionar destino
                        options = ["Não Selecionado"] + [p for p in st.session_state.project['aas_data'].keys()]
                        current_val = mapping['dest'] if mapping['dest'] in options else "Não Selecionado"
                        
                        selected = st.selectbox("Destino AAS", options, index=options.index(current_val), key=f"dest_{p_name}_{m_idx}")
                        
                        # Passo 6: Bloqueio de duplicados
                        if selected != "Não Selecionado" and selected != mapping['dest']:
                            if selected in st.session_state.project['used_properties']:
                                st.error("⚠️ Propriedade já mapeada!")
                            else:
                                # Remove a anterior do set se existir
                                if mapping['dest'] in st.session_state.project['used_properties']:
                                    st.session_state.project['used_properties'].remove(mapping['dest'])
                                mapping['dest'] = selected
                                st.session_state.project['used_properties'].add(selected)

                    with c_del:
                        if st.button("🗑️", key=f"del_{p_name}_{m_idx}"):
                            if mapping['dest'] in st.session_state.project['used_properties']:
                                st.session_state.project['used_properties'].remove(mapping['dest'])
                            st.session_state.project['protocols'][p_name]['mappings'].pop(m_idx)
                            st.rerun()

    with col2:
        st.subheader("AAS Tree")
        # Visualização da Árvore e Destaque
        for prop in st.session_state.project['aas_data'].keys():
            is_used = prop in st.session_state.project['used_properties']
            is_match = st.session_state.search_term.lower() in prop.lower() if st.session_state.search_term else False
            
            style = ""
            if is_match: style += "search-highlight "
            
            label = f"📍 {prop}"
            if is_used:
                st.markdown(f"<div class='{style}' style='opacity: 0.5; text-decoration: line-through;'>{label} (Em uso)</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='{style}'>{label}</div>", unsafe_allow_html=True)

    # Passo 7: Exportar YAML
    st.write("---")
    if st.button("🚀 Exportar YAML Final"):
        yaml_output = yaml.dump(st.session_state.project['protocols'])
        st.download_button("Baixar YAML", yaml_output, "mapping_final.yaml")

else:
    st.info("Aguardando carregamento do AAS (JSON) na barra lateral.")
