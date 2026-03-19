#include <iostream>
#include <string>
#include <zmq.hpp>           
#include <nlohmann/json.hpp> 
#include <chrono>            
#include <thread>            

// O segredo para C++: avisar que estes arquivos são de C puro
extern "C" {
    #include "open62541.h"
}

using json = nlohmann::json;

// Função para pegar o tempo atual em milissegundos
long long get_ms() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
}

// Função para ler dados do servidor OPC UA
double read_opcua_node(UA_Client *client, int node_id) {
    UA_Variant value;
    UA_Variant_init(&value);
    
    // Procura o Nó no Namespace 1
    UA_NodeId id = UA_NODEID_NUMERIC(1, node_id);
    UA_StatusCode status = UA_Client_readValueAttribute(client, id, &value);
    
    if(status == UA_STATUSCODE_GOOD && UA_Variant_hasScalarType(&value, &UA_TYPES[UA_TYPES_DOUBLE])) {
        double val = *(UA_Double*)value.data;
        UA_Variant_clear(&value);
        return val;
    }
    
    UA_Variant_clear(&value);
    return 0.0;
}

int main(int argc, char* argv[]) {
    // Giovana, aqui usamos o ID 2 para a Planta
    int pub_id = (argc > 1) ? std::stoi(argv[1]) : 2; 
    std::string opc_url = (argc > 2) ? argv[2] : "opc.tcp://localhost:4851";
    
    // Configuração ZeroMQ (Publisher)
    zmq::context_t context(1);
    zmq::socket_t publisher(context, ZMQ_PUB);
    publisher.bind("tcp://*:" + std::to_string(5550 + pub_id));

    // Configuração Cliente OPC UA
    UA_Client *client = UA_Client_new();
    UA_ClientConfig_setDefault(UA_Client_getConfig(client));
    
    std::cout << "Conectando ao OPC UA: " << opc_url << "..." << std::endl;
    UA_StatusCode retval = UA_Client_connect(client, opc_url.c_str());
    
    if(retval != UA_STATUSCODE_GOOD) {
        std::cerr << "Erro: Servidor OPC UA na porta 4851 não encontrado!" << std::endl;
        UA_Client_delete(client);
        return (int)retval;
    }

    std::cout << "Publisher [" << pub_id << "] rodando sem erros!" << std::endl;

    while (true) {
        json pos_data = {
            {"pub_id", pub_id},
            {"ts_src", get_ms()},
            {"x", read_opcua_node(client, 1001)}, 
            {"y", read_opcua_node(client, 1002)}
        };
        
        // Envia via ZeroMQ
        publisher.send(zmq::str_buffer("posicao"), zmq::send_flags::sndmore);
        publisher.send(zmq::buffer(pos_data.dump()), zmq::send_flags::none);

        std::this_thread::sleep_for(std::chrono::milliseconds(200)); 
    }

    UA_Client_disconnect(client);
    UA_Client_delete(client);
    return 0;
}
