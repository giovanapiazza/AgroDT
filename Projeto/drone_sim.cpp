#include <zmq.hpp>
#include <string>
#include <iostream>
#include <chrono>
#include <thread>
#include <vector>

/**
 * MOCK DRONE - AGRODT PROJECT
 * Este programa simula o envio de telemetria via ZeroMQ (PUB).
 * Ele alterna entre dados válidos e dados errados para teste de estresse.
 */

int main() {
    // 1. Inicialização do Contexto ZeroMQ
    zmq::context_t context(1);
    
    // 2. Criação do Socket do tipo PUBLISHER
    zmq::socket_t publisher(context, ZMQ_PUB);
    
    // 3. Bind na porta 5555 (A mesma que o Listener está dando Connect)
    try {
        publisher.bind("tcp://*:5555");
        std::cout << "🛸 Simulador Drone AgroDT iniciado com sucesso!" << std::endl;
        std::cout << "📡 Publicando na porta tcp://*:5555" << std::endl;
        std::cout << "------------------------------------------" << std::endl;
    } catch (const zmq::error_t& e) {
        std::cerr << "❌ Erro ao iniciar Socket: " << e.what() << std::endl;
        return 1;
    }

    int cycle_counter = 0;

    while (true) {
        std::string payload;
        std::string test_type;

        // Lógica de alternância de mensagens para o teste
        int test_case = cycle_counter % 3;

        if (test_case == 0) {
            // CASO 1: Mensagem MAVLink 33 (GLOBAL_POSITION_INT) - VÁLIDA
            // Baseada no seu mapping.json
            payload = "{\"msg_id\": 33, \"lat\": -31.3212, \"lon\": -54.1023, \"alt\": 120.5}";
            test_type = "✅ MENSAGEM VÁLIDA (ID 33)";
        } 
        else if (test_case == 1) {
            // CASO 2: ID que não existe no seu mapping.json
            payload = "{\"msg_id\": 999, \"status\": \"unknown_command\"}";
            test_type = "❓ ID DESCONHECIDO (ID 999)";
        } 
        else {
            // CASO 3: JSON Malformado (Simula corrupção de pacote ou erro de rádio)
            payload = "{\"msg_id\": 33, \"lat\": -31.32, corrupt_segment: ...error";
            test_type = "❌ JSON CORROMPIDO (Erro de Sintaxe)";
        }

        // 4. Preparação e Envio do Pacote
        zmq::message_t message(payload.size());
        memcpy(message.data(), payload.data(), payload.size());
        
        publisher.send(message, zmq::send_flags::none);

        // 5. Logging no console do Drone
        std::cout << "[SIMULADOR] Enviando: " << test_type << std::endl;
        std::cout << "  Payload: " << payload << "\n" << std::endl;

        // Incrementa contador e espera 2 segundos para facilitar a leitura no terminal
        cycle_counter++;
        std::this_thread::sleep_for(std::chrono::seconds(2));
    }

    return 0;
}
