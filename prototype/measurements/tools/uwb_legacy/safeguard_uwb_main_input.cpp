// Linux/Pi stdin integration example. It never opens a serial port or drives hardware.
#include "safeguard_uwb_input.hpp"
#include <cerrno>
#include <csignal>
#include <ctime>
#include <iomanip>
#include <iostream>
#include <poll.h>
#include <unistd.h>

namespace {
volatile std::sig_atomic_t stop_requested = 0;
void stop_handler(int) { stop_requested = 1; }
double monotonic_now() {
    timespec ts{};
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) throw std::runtime_error("clock_gettime_failed");
    return ts.tv_sec + ts.tv_nsec / 1e9;
}
}

int main(int argc, char** argv) {
    try {
        std::string peer = "0CA7";
        double timeout = 2.0;
        for (int i = 1; i < argc; ++i) {
            const std::string option = argv[i];
            if (option == "--help") {
                std::cout << "Usage: safeguard_uwb_main_input [--anchor-id 0CA7] [--timeout 2.0]\n"
                          << "Read Python --json output on stdin, on the same Linux/Pi host.\n";
                return 0;
            }
            if (++i >= argc) throw std::runtime_error("missing_option_value");
            if (option == "--anchor-id") peer = argv[i];
            else if (option == "--timeout") {
                std::size_t used = 0; timeout = std::stod(argv[i], &used);
                if (used != std::string(argv[i]).size()) throw std::runtime_error("invalid_timeout");
            } else throw std::runtime_error("unknown_option");
        }
        safeguard::UwbInput input(peer, timeout);
        std::signal(SIGINT, stop_handler); std::signal(SIGTERM, stop_handler);
        std::string pending, last_reason;
        bool dropping = false, last_ready = false;
        double last_print = -1;
        auto show = [&](bool force = false) {
            const double now = monotonic_now(); const auto& s = input.state();
            if (force || s.ready != last_ready || s.reason != last_reason || now - last_print >= 1) {
                if (s.ready) std::cout << "[UWB] READY distance_m=" << std::fixed << std::setprecision(3)
                                      << *s.distance_m << " age_s=" << now - s.rx_monotonic_s << '\n';
                else std::cout << "[UWB] UNAVAILABLE reason=" << s.reason << '\n';
                std::cout.flush(); last_print = now; last_ready = s.ready; last_reason = s.reason;
            }
        };
        show();
        while (!stop_requested) {
            pollfd fd{STDIN_FILENO, POLLIN, 0};
            const int result = poll(&fd, 1, 100);  // Watchdog runs even with a silent pipe.
            if (result < 0 && errno == EINTR) continue;
            if (result < 0 || (fd.revents & (POLLERR | POLLNVAL))) {
                input.invalidate("stdin_error"); show(true); return 1;
            }
            if (fd.revents & (POLLIN | POLLHUP)) {
                char buffer[4096]; const ssize_t size = read(STDIN_FILENO, buffer, sizeof buffer);
                if (size == 0) { input.invalidate("eof"); show(true); return 0; }
                if (size < 0) {
                    if (errno == EINTR) continue;
                    input.invalidate("stdin_error"); show(true); return 1;
                }
                for (ssize_t i = 0; i < size; ++i) {
                    if (buffer[i] == '\n') {
                        if (!dropping) input.ingest(pending, monotonic_now());
                        pending.clear(); dropping = false; show();
                    } else if (!dropping) {
                        pending += buffer[i];
                        if (pending.size() > 16384) {
                            input.invalidate("line_too_long"); pending.clear(); dropping = true; show();
                        }
                    }
                }
            }
            input.tick(monotonic_now()); show();
        }
        input.invalidate("interrupted"); show(true); return 0;
    } catch (const std::exception& error) {
        std::cerr << "UWB input: " << error.what() << '\n'; return 1;
    }
}
