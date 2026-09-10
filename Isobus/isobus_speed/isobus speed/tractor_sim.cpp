#include "demo_common.hpp"
#include "isobus/hardware_integration/can_hardware_interface.hpp"
#include "isobus/hardware_integration/socket_can_interface.hpp"
#include "isobus/isobus/can_network_manager.hpp"
#include "isobus/isobus/isobus_speed_distance_messages.hpp"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <csignal>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
#include <string>
#include <thread>

namespace
{
constexpr std::uint8_t TRACTOR_PREFERRED_ADDRESS = 0xF0;
constexpr std::uint32_t MACHINE_SELECTED_SPEED_PGN = 0xF022;
constexpr std::uint64_t MAX_VALID_DISTANCE_MM = 4211081215ULL;
constexpr double DISTANCE_COUNTER_RANGE_MM = static_cast<double>(MAX_VALID_DISTANCE_MM) + 1.0;
constexpr double MAX_INPUT_SPEED_KMH = 40.0;
constexpr double MAX_ISOBUS_SPEED_MMPS = 64255.0;

std::atomic_bool running(true);
std::atomic<std::uint16_t> selectedSpeedMillimetresPerSecond(0);
std::atomic<std::uint8_t> selectedDirection(
    static_cast<std::uint8_t>(isobus::SpeedMessagesInterface::MachineDirection::Forward));

void signal_handler(int)
{
    running = false;
}

std::uint16_t kmh_to_mmps(double speedKmh)
{
    const double speedMmps = std::abs(speedKmh) * 1000.0 / 3.6;
    const double limited = std::max(0.0, std::min(MAX_ISOBUS_SPEED_MMPS, speedMmps));
    return static_cast<std::uint16_t>(std::lround(limited));
}

double mmps_to_kmh(std::uint16_t speedMmps)
{
    return static_cast<double>(speedMmps) * 3.6 / 1000.0;
}

const char *direction_to_text(isobus::SpeedMessagesInterface::MachineDirection direction)
{
    switch (direction)
    {
        case isobus::SpeedMessagesInterface::MachineDirection::Forward:
            return "frente";
        case isobus::SpeedMessagesInterface::MachineDirection::Reverse:
            return "re";
        case isobus::SpeedMessagesInterface::MachineDirection::Error:
            return "erro";
        case isobus::SpeedMessagesInterface::MachineDirection::NotAvailable:
        default:
            return "indisponivel";
    }
}
}

int main()
{
    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);

    const std::string canInterfaceName = demo::get_can_interface_name();
    auto canDriver = std::make_shared<isobus::SocketCANInterface>(canInterfaceName);
    isobus::CANHardwareInterface::set_number_of_can_channels(1);
    isobus::CANHardwareInterface::assign_can_channel_frame_handler(0, canDriver);

    if ((!isobus::CANHardwareInterface::start()) || (!canDriver->get_is_valid()))
    {
        std::cerr << "Erro: nao foi possivel abrir a interface " << canInterfaceName << ".\n";
        return 1;
    }

    isobus::NAME tractorName(0);
    tractorName.set_arbitrary_address_capable(true);
    tractorName.set_industry_group(static_cast<std::uint8_t>(
        isobus::NAME::IndustryGroup::AgriculturalAndForestryEquipment));
    tractorName.set_device_class(static_cast<std::uint8_t>(
        isobus::NAME::DeviceClass::NonSpecific));
    tractorName.set_function_code(static_cast<std::uint8_t>(
        isobus::NAME::Function::TractorECU));
    tractorName.set_identity_number(1001);
    tractorName.set_ecu_instance(0);
    tractorName.set_function_instance(0);
    tractorName.set_device_class_instance(0);
    tractorName.set_manufacturer_code(1407);

    auto tractorECU = isobus::CANNetworkManager::CANNetwork.create_internal_control_function(
        tractorName,
        0,
        TRACTOR_PREFERRED_ADDRESS);

    if (!demo::wait_for_address_claim(tractorECU, running, std::chrono::seconds(5)))
    {
        if (running)
        {
            std::cerr << "Erro: a TECU nao conseguiu reivindicar um endereco ISOBUS.\n";
        }
        isobus::CANHardwareInterface::stop();
        return running ? 2 : 130;
    }

    isobus::SpeedMessagesInterface speedInterface(
        tractorECU,
        false,
        false,
        true,
        false);

    speedInterface.machineSelectedSpeedTransmitData.set_speed_source(
        isobus::SpeedMessagesInterface::MachineSelectedSpeedData::SpeedSource::Simulated);
    speedInterface.machineSelectedSpeedTransmitData.set_limit_status(
        isobus::SpeedMessagesInterface::MachineSelectedSpeedData::LimitStatus::NotLimited);
    speedInterface.machineSelectedSpeedTransmitData.set_exit_reason_code(
        static_cast<std::uint8_t>(
            isobus::SpeedMessagesInterface::MachineSelectedSpeedData::ExitReasonCode::NoReasonAllClear));
    speedInterface.machineSelectedSpeedTransmitData.set_machine_direction_of_travel(
        isobus::SpeedMessagesInterface::MachineDirection::Forward);
    speedInterface.initialize();

    std::thread networkThread([&speedInterface]() {
        double distanceAccumulatorMm = 0.0;
        auto previousTime = std::chrono::steady_clock::now();

        while (running)
        {
            const auto currentTime = std::chrono::steady_clock::now();
            const double elapsedSeconds =
                std::chrono::duration<double>(currentTime - previousTime).count();
            previousTime = currentTime;

            const std::uint16_t speedMmps = selectedSpeedMillimetresPerSecond.load();
            distanceAccumulatorMm += static_cast<double>(speedMmps) * elapsedSeconds;

            if (distanceAccumulatorMm >= DISTANCE_COUNTER_RANGE_MM)
            {
                distanceAccumulatorMm = std::fmod(distanceAccumulatorMm, DISTANCE_COUNTER_RANGE_MM);
            }

            const auto direction = static_cast<isobus::SpeedMessagesInterface::MachineDirection>(
                selectedDirection.load());

            speedInterface.machineSelectedSpeedTransmitData.set_machine_speed(speedMmps);
            speedInterface.machineSelectedSpeedTransmitData.set_machine_distance(
                static_cast<std::uint32_t>(distanceAccumulatorMm));
            speedInterface.machineSelectedSpeedTransmitData.set_machine_direction_of_travel(direction);
            speedInterface.update();

            std::this_thread::sleep_for(std::chrono::milliseconds(10));
        }
    });

    const std::uint8_t claimedAddress = tractorECU->get_address();
    const std::uint32_t exampleCanIdentifier =
        (3UL << 26) | (MACHINE_SELECTED_SPEED_PGN << 8) | claimedAddress;

    std::cout << "\n=== SIMULADOR DA TECU DO TRATOR ===\n";
    std::cout << "Interface CAN             : " << canInterfaceName << "\n";
    std::cout << "Endereco ISOBUS           : 0x"
              << std::hex << std::uppercase << static_cast<int>(claimedAddress) << "\n";
    std::cout << "NAME                      : IG=2, DeviceClass=0, Function=134 (Tractor ECU)\n";
    std::cout << "PGN transmitido           : 0xF022 / 61474 - Machine Selected Speed\n";
    std::cout << "CAN ID atual, prioridade 3: 0x" << std::setw(8) << std::setfill('0')
              << exampleCanIdentifier << std::setfill(' ') << std::dec << "\n";
    std::cout << "Fonte informada no SPN    : Simulated\n";
    std::cout << "Periodo da mensagem       : 100 ms, controlado pela AgIsoStack++\n\n";
    std::cout << "Digite uma velocidade entre -40 e 40 km/h.\n";
    std::cout << "Valores negativos simulam marcha a re; 0 mantem a ultima direcao.\n";
    std::cout << "Digite q para sair.\n\n";

    std::string input;
    while (running)
    {
        std::cout << "Velocidade do trator [km/h] > " << std::flush;
        if (!std::getline(std::cin, input))
        {
            running = false;
            break;
        }

        if ((input == "q") || (input == "Q"))
        {
            running = false;
            break;
        }

        std::istringstream parser(input);
        double speedKmh = 0.0;
        char trailingCharacter = '\0';
        if (!(parser >> speedKmh) || (parser >> trailingCharacter) ||
            (speedKmh < -MAX_INPUT_SPEED_KMH) || (speedKmh > MAX_INPUT_SPEED_KMH))
        {
            std::cout << "Valor invalido. Use um numero entre -40 e 40.\n";
            continue;
        }

        if (speedKmh > 0.0)
        {
            selectedDirection = static_cast<std::uint8_t>(
                isobus::SpeedMessagesInterface::MachineDirection::Forward);
        }
        else if (speedKmh < 0.0)
        {
            selectedDirection = static_cast<std::uint8_t>(
                isobus::SpeedMessagesInterface::MachineDirection::Reverse);
        }

        const std::uint16_t speedMmps = kmh_to_mmps(speedKmh);
        selectedSpeedMillimetresPerSecond = speedMmps;
        const auto direction = static_cast<isobus::SpeedMessagesInterface::MachineDirection>(
            selectedDirection.load());

        std::cout << "TECU atualizada: " << std::fixed << std::setprecision(1)
                  << mmps_to_kmh(speedMmps) << " km/h, direcao "
                  << direction_to_text(direction) << " (" << speedMmps << " mm/s).\n\n";
    }

    running = false;
    if (networkThread.joinable())
    {
        networkThread.join();
    }

    isobus::CANHardwareInterface::stop();
    std::cout << "Simulador do trator encerrado.\n";
    return 0;
}
