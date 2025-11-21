#include <ctime>
#include <sstream>
#include <string>

namespace {

std::string current_timestamp() {
    std::time_t now = std::time(nullptr);
    char buf[64];
    std::strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", std::gmtime(&now));
    return std::string(buf);
}

int write_json(const std::string& payload, char* result_buf, int buf_size) {
    if (static_cast<int>(payload.size()) + 1 > buf_size) {
        return -1;
    }
    std::snprintf(result_buf, buf_size, "%s", payload.c_str());
    return 0;
}

}  // namespace

extern "C" {

int cpp_game_query(const char* query, char* result_buf, int buf_size) {
    std::ostringstream oss;
    oss << R"({"domain":"game","query":")" << query
        << R"(","status":"stub","timestamp":")" << current_timestamp() << R"("})";
    return write_json(oss.str(), result_buf, buf_size);
}

int cpp_discord_status(char* result_buf, int buf_size) {
    std::ostringstream oss;
    oss << R"({"domain":"discord","status":"online","timestamp":")" << current_timestamp()
        << R"("})";
    return write_json(oss.str(), result_buf, buf_size);
}

}
