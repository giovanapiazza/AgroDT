#include <iostream>
#include <fstream>
#include <string>
#include <zmq.hpp>
#include <nlohmann/json.hpp>
#include <chrono>

using json = nlohmann::json;

// Função para obter o tempo em milissegundos
long long get_ms() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
}

int main(int argc, char* argv[]) {
    int sub_id = (argc > 1) ? std::stoi(argv[1]) : 1;
    std::string profile = (argc > 2) ? argv[2] : "S3";

    zmq::context_t context(1);
    zmq::socket_t subscriber(context, ZMQ_SUB);

    // Conecta nos dois ativos (UAV e Planta)
    subscriber.connect("tcp://localhost:5551");
    subscriber.connect("tcp://localhost:5552");

    if (profile == "S1") {
        subscriber.set(zmq::sockopt::subscribe, "posicao");
    } else if (profile == "S2") {
        subscriber.set(zmq::sockopt::subscribe, "cinematica");
    } else {
        subscriber.set(zmq::sockopt::subscribe, ""); 
    }

    std::ofstream csv("metricas_S" + std::to_string(sub_id) + ".csv");
    csv << "sub_id,pub_id,topic,seq,ts_src,ts_rx,latencia_ms\n";

    std::cout << "Subscriber S" << sub_id << " monitorando AgroDT..." << std::endl;

    while (true) {
        zmq::message_t topic_msg, payload_msg;
        
        // CORREÇÃO: Armazenamos o resultado para evitar o erro 'nodiscard'
        auto res1 = subscriber.recv(topic_msg, zmq::recv_flags::none);
        auto res2 = subscriber.recv(payload_msg, zmq::recv_flags::none);

        if (res1 && res2) {
            long long ts_rx = get_ms();
            std::string topic = std::string(static_cast<char*>(topic_msg.data()), topic_msg.size());
            std::string payload = std::string(static_cast<char*>(payload_msg.data()), payload_msg.size());

            try {
                json data = json::parse(payload);
                long long ts_src = data["ts_src"];
                long long latencia = ts_rx - ts_src;

                csv << sub_id << "," << data["pub_id"] << "," << topic << "," 
                    << data["seq"] << "," << ts_src << "," << ts_rx << "," 
                    << latencia << "\n" << std::flush;

                std::cout << "[Recebido] Ativo: " << data["pub_id"] << " | Tópico: " << topic 
                          << " | Latência: " << latencia << "ms" << std::endl;

            } catch (json::parse_error& e) {
                std::cerr << "Erro no JSON: " << e.what() << std::endl;
            }
        }
    }
    return 0;
}
