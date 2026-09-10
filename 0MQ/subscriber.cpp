#include <zmq.hpp>
#include <iostream>
#include <string>

int main() {
    zmq::context_t context(1);
    zmq::socket_t subscriber(context, ZMQ_SUB);

    // Conecta ao endereço do simulador
    subscriber.connect("tcp://localhost:5555");

    // " " significa que queremos receber todas as mensagens (sem filtro)
    subscriber.set(zmq::sockopt::subscribe, "");

    std::cout << "📡 Listener AgroDT aguardando mensagens..." << std::endl;

    while (true) {
        zmq::message_t update;
        auto res = subscriber.recv(update, zmq::recv_flags::none);

        if (res) {
            std::string msg_str(static_cast<char*>(update.data()), update.size());
            
            // LOGGING INICIAL: Validação de integridade
            std::cout << "[LOG] Recebido (" << update.size() << " bytes): " 
                      << msg_str << std::endl;
            
            // Próximo passo (Quarta-feira): Inserir aqui a lógica de parsing
        }
    }

    return 0;
}
