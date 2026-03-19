#include <zmq.hpp>
#include <iostream>
#include <fstream>
#include "include/json.hpp"

using json = nlohmann::json;

// Função para buscar o mapeamento no JSON
void process_message(const json& incoming_msg, const json& mapping_rules) {
    int id = incoming_msg["msg_id"];
    bool found = false;

    for (auto& m : mapping_rules["mappings"]) {
        if (m["mavlink_id"] == id) {
            found = true;
            std::cout << "🎯 Match encontrado: " << m["mavlink_name"] << std::endl;
            
            for (auto& f : m["fields"]) {
                std::string field_name = f["mavlink_field"];
                if (incoming_msg.contains(field_name)) {
                    // Aqui acontece o Mapeamento Dinâmico para OPC UA
                    std::cout << "  [MAP] Campo '" << field_name 
                              << "' -> Node: " << m["opc_ua_base_node"].get<std::string>() 
                              << f["opc_node"].get<std::string>()
                              << " | Valor: " << incoming_msg[field_name] << std::endl;
                }
            }
        }
    }
    if (!found) std::cout << "⚠️ Mensagem ID " << id << " ignorada (não mapeada)." << std::endl;
}

int main() {
    // Carregar arquivo de mapeamento
    std::ifstream file("mapping.json");
    if (!file.is_open()) {
        std::cerr << "Erro ao abrir mapping.json!" << std::endl;
        return 1;
    }
    json mapping_rules = json::parse(file);

    // Setup ZeroMQ
    zmq::context_t context(1);
    zmq::socket_t subscriber(context, ZMQ_SUB);
    subscriber.connect("tcp://localhost:5555");
    subscriber.set(zmq::sockopt::subscribe, "");

    std::cout << "📡 AgroDT Listener Iniciado..." << std::endl;

    while (true) {
        zmq::message_t msg;
        auto res = subscriber.recv(msg, zmq::recv_flags::none);
        if (res) {
            try {
                std::string r_str(static_cast<char*>(msg.data()), msg.size());
                json incoming = json::parse(r_str);
                process_message(incoming, mapping_rules);
            } catch (json::parse_error& e) {
                std::cerr << "❌ Erro de integridade/corrupção de dados!" << std::endl;
            }
        }
    }
    return 0;
}

