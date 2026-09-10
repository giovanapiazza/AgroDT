import asyncio
from asyncua import Client

# Função interna assíncrona (privada)
async def _async_ler_sensor(url, node_id):
    async with Client(url=url) as client:
        # Acessa o nó e lê o valor
        node = client.get_node(node_id)
        valor = await node.read_value()
        return valor

# Função exposta para o Streamlit (Síncrona)
def ler_sensor_opcua(url, node_id):
    """
    Função que o Streamlit chama. Ela encapsula a complexidade 
    da async/await dentro de um 'run'.
    """
    try:
        return asyncio.run(_async_ler_sensor(url, node_id))
    except Exception as e:
        return f"Erro na conexão: {e}"
