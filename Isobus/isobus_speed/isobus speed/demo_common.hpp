#ifndef ISOBUS_SPEED_DEMO_COMMON_HPP
#define ISOBUS_SPEED_DEMO_COMMON_HPP

#include <atomic>
#include <chrono>
#include <cstdlib>
#include <string>
#include <thread>

namespace demo
{
inline std::string get_can_interface_name()
{
    const char *configuredInterface = std::getenv("ISOBUS_CAN_INTERFACE");
    if ((nullptr != configuredInterface) && ('\0' != configuredInterface[0]))
    {
        return configuredInterface;
    }
    return "can0";
}

template<typename ControlFunctionPointer>
bool wait_for_address_claim(const ControlFunctionPointer &controlFunction,
                            const std::atomic_bool &running,
                            std::chrono::milliseconds timeout)
{
    const auto deadline = std::chrono::steady_clock::now() + timeout;
    while (running && !controlFunction->get_address_valid())
    {
        if (std::chrono::steady_clock::now() >= deadline)
        {
            return false;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(25));
    }
    return running && controlFunction->get_address_valid();
}
}

#endif
