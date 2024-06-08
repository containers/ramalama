#include <string>
#include <vector>
#include <cstring>

struct ModelFile {
    std::string from;
    std::vector<std::pair<std::string, std::string>> parameters;
    std::string template_str;
    std::string system;
    std::string adapter;
    std::string license;
    std::vector<std::pair<std::string, std::string>> messages;
};

bool starts_with(const std::string& str, const std::string& prefix) {
    return str.substr(0, prefix.size()) == prefix;
}

std::string read_multiline(FILE* file) {
    std::string result;
    char buffer[1024];

    while (std::fgets(buffer, sizeof(buffer), file)) {
        std::string line(buffer);
        result += line;
        if (line.find("\"\"\"") != std::string::npos) {
            break;
        }
    }

    // Remove the trailing newline character if present
    if (!result.empty() && result.back() == '\n') {
        result.pop_back();
    }

    return result;
}

void parse_line(const std::string& line, ModelFile& model, FILE* file) {
    if (starts_with(line, "FROM ")) {
        model.from = line.substr(5);
    } else if (starts_with(line, "PARAMETER ")) {
        size_t space_pos = line.find(' ', 10);
        if (space_pos != std::string::npos) {
            std::string param = line.substr(10, space_pos - 10);
            std::string value = line.substr(space_pos + 1);
            model.parameters.emplace_back(param, value);
        }
    } else if (starts_with(line, "TEMPLATE ")) {
        model.template_str = line.substr(9);
    } else if (starts_with(line, "SYSTEM ")) {
        model.system = line.substr(7);
        if (model.system.find("\"\"\"") != std::string::npos) {
            model.system += "\n" + read_multiline(file);
        }
    } else if (starts_with(line, "ADAPTER ")) {
        model.adapter = line.substr(8);
    } else if (starts_with(line, "LICENSE ")) {
        model.license = line.substr(8);
        if (model.license.find("\"\"\"") != std::string::npos) {
            model.license += "\n" + read_multiline(file);
        }
    } else if (starts_with(line, "MESSAGE ")) {
        size_t space_pos = line.find(' ', 8);
        if (space_pos != std::string::npos) {
            std::string role = line.substr(8, space_pos - 8);
            std::string message = line.substr(space_pos + 1);
            model.messages.emplace_back(role, message);
        }
    }
}

ModelFile parse_modelfile(const std::string& filename) {
    ModelFile model;
    FILE* file = std::fopen(filename.c_str(), "r");
    if (!file) {
        return model; // Return empty model on error
    }

    char buffer[1024];
    while (std::fgets(buffer, sizeof(buffer), file)) {
        std::string line(buffer);
        // Remove newline character
        line.erase(line.find_last_not_of(" \n\r\t") + 1);
        if (line.empty() || line[0] == '#') {
            continue;
        }
        parse_line(line, model, file);
    }

    std::fclose(file);
    return model;
}

int main() {
    const std::string filename = "Modelfile";
    ModelFile model = parse_modelfile(filename);

    // Output parsed values for verification
    printf("FROM: %s\n", model.from.c_str());
    for (const auto& param : model.parameters) {
        printf("PARAMETER %s: %s\n", param.first.c_str(), param.second.c_str());
    }
    printf("TEMPLATE: %s\n", model.template_str.c_str());
    printf("SYSTEM: %s\n", model.system.c_str());
    printf("ADAPTER: %s\n", model.adapter.c_str());
    printf("LICENSE: %s\n", model.license.c_str());
    for (const auto& msg : model.messages) {
        printf("MESSAGE %s: %s\n", msg.first.c_str(), msg.second.c_str());
    }

    return 0;
}

