// mips_simulator.cpp

#include <iostream>
#include <fstream>
#include <sstream>
#include <bitset>
#include <vector>
#include <unordered_map>
#include <iomanip>
#include <string>
#include <algorithm>
#include <iterator>
#include <cctype>
#include <cmath>
#include <climits>

// Enum to keep track of the current section
enum Section { UNKNOWN, DATA, TEXT };

// Struct to hold data items
struct DataItem {
    int address;
    std::vector<int> values; // To handle arrays
};

// Function to remove comments and trim whitespace, and track the current section
std::string preprocessLine(const std::string& line, Section& currentSection) {
    std::string processed = line;
    // Remove comments
    size_t commentPos = processed.find('#');
    if (commentPos != std::string::npos) {
        processed = processed.substr(0, commentPos);
    }
    // Trim whitespace
    processed.erase(processed.begin(),
                    std::find_if(processed.begin(), processed.end(), [](unsigned char ch) { return !std::isspace(ch); }));
    processed.erase(std::find_if(processed.rbegin(), processed.rend(), [](unsigned char ch) { return !std::isspace(ch); }).base(),
                    processed.end());

    if (processed.empty()) {
        return processed;
    }

    // Check for section directives
    if (processed == ".data") {
        currentSection = DATA;
        return "";  // Return empty line since .data is a directive
    } else if (processed == ".text") {
        currentSection = TEXT;
        return "";  // Return empty line since .text is a directive
    } else if (processed[0] == '.') {
        // Handle other directives if necessary
        return processed;
    }

    return processed;
}

// Function to parse a register name (e.g., $t0) and return its number
int parseRegister(const std::string& reg) {
    if (reg[0] != '$') {
        std::cerr << "Invalid register: " << reg << "\n";
        exit(1);
    }
    std::string regName = reg.substr(1);

    // Mapping of register names to numbers
    static std::unordered_map<std::string, int> regMap = {
        {"zero", 0}, {"0", 0},
        {"at", 1}, {"1", 1},
        {"v0", 2}, {"2", 2}, {"v1", 3}, {"3", 3},
        {"a0", 4}, {"4", 4}, {"a1", 5}, {"5", 5}, {"a2", 6}, {"6", 6}, {"a3", 7}, {"7", 7},
        {"t0", 8}, {"8", 8}, {"t1", 9}, {"9", 9}, {"t2", 10}, {"10", 10}, {"t3", 11}, {"11", 11},
        {"t4", 12}, {"12", 12}, {"t5", 13}, {"13", 13}, {"t6", 14}, {"14", 14}, {"t7", 15}, {"15", 15},
        {"s0", 16}, {"16", 16}, {"s1", 17}, {"17", 17}, {"s2", 18}, {"18", 18}, {"s3", 19}, {"19", 19},
        {"s4", 20}, {"20", 20}, {"s5", 21}, {"21", 21}, {"s6", 22}, {"22", 22}, {"s7", 23}, {"23", 23},
        {"t8", 24}, {"24", 24}, {"t9", 25}, {"25", 25},
        {"k0", 26}, {"26", 26}, {"k1", 27}, {"27", 27},
        {"gp", 28}, {"28", 28}, {"sp", 29}, {"29", 29}, {"fp", 30}, {"30", 30}, {"ra", 31}, {"31", 31}
    };

    if (regMap.find(regName) != regMap.end()) {
        return regMap[regName];
    } else {
        std::cerr << "Unknown register: " << reg << "\n";
        exit(1);
    }
}

// Function to parse an immediate value (supports label+offset, decimal, and hex)
int parseImmediate(const std::string& immStr, const std::unordered_map<std::string, DataItem>& dataSymbolTable) {
    int imm = 0;
    size_t plusPos = immStr.find('+');
    size_t minusPos = immStr.find('-', 1); // Start search from position 1 to avoid negative numbers
    try {
        if (plusPos != std::string::npos) {
            // Handle label + offset
            std::string label = immStr.substr(0, plusPos);
            std::string offsetStr = immStr.substr(plusPos + 1);
            int offset = std::stoi(offsetStr);
            if (dataSymbolTable.count(label)) {
                imm = dataSymbolTable.at(label).address + offset;
            } else {
                std::cerr << "Undefined label: " << label << "\n";
                exit(1);
            }
        } else if (minusPos != std::string::npos) {
            // Handle label - offset
            std::string label = immStr.substr(0, minusPos);
            std::string offsetStr = immStr.substr(minusPos);
            int offset = std::stoi(offsetStr);
            if (dataSymbolTable.count(label)) {
                imm = dataSymbolTable.at(label).address + offset; // offset is negative
            } else {
                std::cerr << "Undefined label: " << label << "\n";
                exit(1);
            }
        } else if (dataSymbolTable.count(immStr)) {
            // Label only
            imm = dataSymbolTable.at(immStr).address;
        } else if (immStr.substr(0, 2) == "0x" || immStr.substr(0, 2) == "0X") {
            // Hexadecimal immediate
            imm = std::stoi(immStr, nullptr, 16);
        } else if (immStr.substr(0, 1) == "-" || std::isdigit(immStr[0])) {
            // Decimal immediate
            imm = std::stoi(immStr);
        } else {
            std::cerr << "Invalid immediate value: " << immStr << "\n";
            exit(1);
        }
    } catch (const std::invalid_argument& e) {
        std::cerr << "Invalid immediate value: " << immStr << "\n";
        exit(1);
    } catch (const std::out_of_range& e) {
        std::cerr << "Immediate value out of range: " << immStr << "\n";
        exit(1);
    }
    return imm;
}

// Function to assemble an instruction into binary code
std::vector<std::string> assembleInstruction(const std::string& instructionLine, int lineNumber,
                                             std::unordered_map<std::string, int>& labelAddresses,
                                             const std::unordered_map<std::string, int>& opcodes,
                                             const std::unordered_map<std::string, int>& functCodes,
                                             const std::unordered_map<std::string, std::string>& instructionTypes,
                                             const std::unordered_map<std::string, DataItem>& dataSymbolTable) {
    // Initialize a vector to hold the binary codes (to accommodate pseudo-instructions expanding into multiple instructions)
    std::vector<std::string> binaryCodes;

    // Remove comments
    size_t commentPos = instructionLine.find('#');
    std::string instruction = instructionLine;
    if (commentPos != std::string::npos) {
        instruction = instructionLine.substr(0, commentPos);
    }
    // Remove commas and split the instruction into parts
    instruction.erase(std::remove(instruction.begin(), instruction.end(), ','), instruction.end());
    std::istringstream iss(instruction);
    std::vector<std::string> parts{std::istream_iterator<std::string>{iss},
                                   std::istream_iterator<std::string>{}};

    if (parts.empty()) {
        return binaryCodes;
    }

    // Check for label definitions (e.g., "loop:")
    if (parts[0].back() == ':') {
        std::string label = parts[0].substr(0, parts[0].length() - 1);
        labelAddresses[label] = lineNumber;
        parts.erase(parts.begin());
        if (parts.empty()) {
            // The line is just a label
            return binaryCodes;
        }
    }

    if (parts.empty()) {
        return binaryCodes;
    }

    std::string opcodeStr = parts[0];
    std::string binaryCode;

    // Handling for instructions
    auto instrTypeIt = instructionTypes.find(opcodeStr);
    if (instrTypeIt == instructionTypes.end()) {
        std::cerr << "Unsupported instruction: " << opcodeStr << "\n";
        exit(1);
    }
    std::string instrType = instrTypeIt->second;

    if (instrType == "R") {
        // R-type instruction
        int rs = 0, rt = 0, rd = 0, shamt = 0, funct = 0;
        int opcode = 0;  // Opcode for R-type instructions is 0

        if (functCodes.find(opcodeStr) == functCodes.end()) {
            std::cerr << "Unsupported R-type instruction: " << opcodeStr << "\n";
            exit(1);
        }
        funct = functCodes.at(opcodeStr);

        if (opcodeStr == "sll" || opcodeStr == "srl" || opcodeStr == "sra") {
            // Shift instructions: sll rd, rt, shamt
            if (parts.size() != 4) {
                std::cerr << "Invalid format for instruction: " << instructionLine << "\n";
                exit(1);
            }
            rd = parseRegister(parts[1]);
            rt = parseRegister(parts[2]);
            shamt = parseImmediate(parts[3], dataSymbolTable);

        } else if (opcodeStr == "jr") {
            // Jump register instruction: jr rs
            if (parts.size() != 2) {
                std::cerr << "Invalid format for instruction: " << instructionLine << "\n";
                exit(1);
            }
            rs = parseRegister(parts[1]);

        } else if (opcodeStr == "jalr") {
            // Jump and link register: jalr rd, rs
            if (parts.size() == 2) {
                rs = parseRegister(parts[1]);
                rd = 31; // Default return address register
            } else if (parts.size() == 3) {
                rd = parseRegister(parts[1]);
                rs = parseRegister(parts[2]);
            } else {
                std::cerr << "Invalid format for instruction: " << instructionLine << "\n";
                exit(1);
            }

        } else {
            // All other R-type instructions: rd, rs, rt
            if (parts.size() != 4) {
                std::cerr << "Invalid format for instruction: " << instructionLine << "\n";
                exit(1);
            }
            rd = parseRegister(parts[1]);
            rs = parseRegister(parts[2]);
            rt = parseRegister(parts[3]);
        }

        std::bitset<6> opcodeBits(opcode);
        std::bitset<5> rsBits(rs);
        std::bitset<5> rtBits(rt);
        std::bitset<5> rdBits(rd);
        std::bitset<5> shamtBits(shamt);
        std::bitset<6> functBits(funct);

        binaryCode = opcodeBits.to_string() + rsBits.to_string() + rtBits.to_string() +
                     rdBits.to_string() + shamtBits.to_string() + functBits.to_string();
        binaryCodes.push_back(binaryCode);

    } else if (instrType == "I") {
        // I-type instruction
        int opcode = opcodes.at(opcodeStr);
        int rs = 0, rt = 0;
        int immediate = 0;

        if (opcodeStr == "lw" || opcodeStr == "sw" || opcodeStr == "lb" || opcodeStr == "sb" ||
            opcodeStr == "lui" || opcodeStr == "lh" || opcodeStr == "sh" || opcodeStr == "lbu" || opcodeStr == "lhu") {

            if (opcodeStr == "lui") {
                // Load upper immediate: lui rt, immediate
                if (parts.size() != 3) {
                    std::cerr << "Invalid format for instruction: " << instructionLine << "\n";
                    exit(1);
                }
                rt = parseRegister(parts[1]);
                immediate = parseImmediate(parts[2], dataSymbolTable);
            } else {
                // Memory instructions: rt, immediate(rs) or rt, label
                if (parts.size() != 3) {
                    std::cerr << "Invalid format for instruction: " << instructionLine << "\n";
                    exit(1);
                }
                rt = parseRegister(parts[1]);
                size_t start = parts[2].find('(');
                size_t end = parts[2].find(')');
                if (start != std::string::npos && end != std::string::npos) {
                    // Format: offset(register)
                    std::string offsetStr = parts[2].substr(0, start);
                    immediate = parseImmediate(offsetStr, dataSymbolTable);
                    rs = parseRegister(parts[2].substr(start + 1, end - start - 1));
                } else {
                    // Format: label or immediate
                    immediate = parseImmediate(parts[2], dataSymbolTable);
                    rs = 0;
                }
            }

        } else if (opcodeStr == "beq" || opcodeStr == "bne" || opcodeStr == "blez" || opcodeStr == "bgtz" ||
                   opcodeStr == "bltz" || opcodeStr == "bgez") {

            if (opcodeStr == "beq" || opcodeStr == "bne") {
                if (parts.size() != 4) {
                    std::cerr << "Invalid format for instruction: " << instructionLine << "\n";
                    exit(1);
                }
                rs = parseRegister(parts[1]);
                rt = parseRegister(parts[2]);
                // Calculate offset
                int labelAddress;
                if (labelAddresses.count(parts[3])) {
                    labelAddress = labelAddresses[parts[3]];
                    immediate = labelAddress - (lineNumber + 1);
                } else {
                    std::cerr << "Undefined label: " << parts[3] << "\n";
                    exit(1);
                }
            } else {
                if (parts.size() != 3) {
                    std::cerr << "Invalid format for instruction: " << instructionLine << "\n";
                    exit(1);
                }
                rs = parseRegister(parts[1]);
                rt = 0;
                int labelAddress;
                if (labelAddresses.count(parts[2])) {
                    labelAddress = labelAddresses[parts[2]];
                    immediate = labelAddress - (lineNumber + 1);
                } else {
                    std::cerr << "Undefined label: " << parts[2] << "\n";
                    exit(1);
                }
            }

        } else {
            // Immediate arithmetic/logical instructions: rt, rs, immediate
            if (parts.size() != 4) {
                std::cerr << "Invalid format for instruction: " << instructionLine << "\n";
                exit(1);
            }
            rt = parseRegister(parts[1]);
            rs = parseRegister(parts[2]);
            immediate = parseImmediate(parts[3], dataSymbolTable);
        }

        std::bitset<6> opcodeBits(opcode);
        std::bitset<5> rsBits(rs);
        std::bitset<5> rtBits(rt);
        std::bitset<16> immBits(immediate);

        binaryCode = opcodeBits.to_string() + rsBits.to_string() + rtBits.to_string() + immBits.to_string();
        binaryCodes.push_back(binaryCode);

    } else if (instrType == "J") {
        // J-type instruction
        int opcode = opcodes.at(opcodeStr);
        int address;

        if (parts.size() != 2) {
            std::cerr << "Invalid format for instruction: " << instructionLine << "\n";
            exit(1);
        }

        if (labelAddresses.count(parts[1])) {
            address = labelAddresses[parts[1]];
        } else {
            std::cerr << "Undefined label: " << parts[1] << "\n";
            exit(1);
        }

        std::bitset<6> opcodeBits(opcode);
        std::bitset<26> addrBits(address);

        binaryCode = opcodeBits.to_string() + addrBits.to_string();
        binaryCodes.push_back(binaryCode);

    } else {
        // Handle other instruction types...
        std::cerr << "Unsupported instruction type: " << instrType << "\n";
        exit(1);
    }

    return binaryCodes;
}

// Function to print the register values
void printRegisters(const std::unordered_map<std::string, int>& reg) {
    std::cout << "Registers:\n";
    for (int i = 0; i < 32; i += 4) {  // Print 4 registers per line
        for (int j = 0; j < 4; ++j) {
            std::string regName = "$" + std::to_string(i + j);
            int value = reg.at(regName);
            std::cout << std::setw(4) << regName << ": " << std::setw(10) << value << " | ";
        }
        std::cout << "\n";
    }
    std::cout << "\n";
}

// Function to print the memory values
void printMemory(const std::unordered_map<int, int>& memory) {
    std::cout << "Memory:\n";

    // Find the range of memory addresses to display
    std::vector<int> addresses;
    for (const auto& [address, value] : memory) {
        if (value != 0) {
            addresses.push_back(address);
        }
    }

    if (addresses.empty()) {
        std::cout << "\nAll memory values are 0.\n\n";
        return;
    }

    int minAddress = *std::min_element(addresses.begin(), addresses.end());
    int maxAddress = *std::max_element(addresses.begin(), addresses.end());

    // Align the start address to the nearest multiple of 4
    int startAddress = minAddress - (minAddress % 4);

    // Ensure at least 32 addresses are displayed
    while (maxAddress - startAddress < 32 * 4) {
        maxAddress += 4;
    }

    // Print the memory values
    for (int address = startAddress; address <= maxAddress; address += 16) {
        for (int offset = 0; offset < 16; offset += 4) {
            int currentAddress = address + offset;
            int value = memory.count(currentAddress) ? memory.at(currentAddress) : 0;
            std::cout << "M[" << std::setw(10) << currentAddress << "]: " << std::setw(10) << value << " | ";
        }
        std::cout << "\n";
    }

    std::cout << "\n";
}

// Function to simulate the execution of MIPS instructions
void simulate(const std::vector<std::string>& asmList,
              const std::vector<std::string>& binList,
              const std::unordered_map<std::string, int>& labelAddresses,
              const std::unordered_map<std::string, DataItem>& dataSymbolTable,
              std::unordered_map<int, int>& memory) {
    // Simulated memory passed by reference to preserve data declarations

    std::unordered_map<std::string, int> reg;
    // Initialize registers
    for (int i = 0; i < 32; ++i) {
        reg["$" + std::to_string(i)] = 0;
    }
    reg["$29"] = 0x7FFFFFFC; // Initialize stack pointer ($sp)

    int PC = 0; // Instruction index
    std::unordered_map<std::string, int> counts = {
        {"Total", 0},
        {"ALU", 0},
        {"Jump", 0},
        {"Branch", 0},
        {"Memory", 0},
        {"Other", 0},
        {"Special", 0}
    };

    std::cout << "Enter 'n' for single instruction mode, 'a' for automatic mode: ";
    char mode;
    std::cin >> mode;
    bool single_step = (mode == 'n');

    int numInstructions = static_cast<int>(asmList.size());

    while (PC < numInstructions) {
        std::string curr = asmList[PC];
        std::string binCode = binList[PC];

        // Remove commas and split the instruction into parts
        std::string line = curr;
        // Remove comments
        size_t commentPos = line.find('#');
        if (commentPos != std::string::npos) {
            line = line.substr(0, commentPos);
        }
        line.erase(std::remove(line.begin(), line.end(), ','), line.end());
        std::istringstream iss(line);
        std::vector<std::string> parts{std::istream_iterator<std::string>{iss},
                                       std::istream_iterator<std::string>{}};

        if (parts.empty()) {
            PC += 1;
            continue;
        }

        if (single_step) {
            std::cout << "\n" << std::string(80, '=') << "\n";
            std::cout << "Executing Instruction:\n";
            std::cout << "Line " << PC << ": " << curr << "\n";
            if (!binCode.empty()) {
                std::cout << "Machine Code: " << binCode << "\n";
            }
            std::cout << "PC before execution: " << PC << "\n";
        }

        std::string opcodeStr = parts[0];

        // Handling for instructions
        try {
            if (opcodeStr == "add") {
                // R-type ALU instruction
                int rd = parseRegister(parts[1]);
                int rs = parseRegister(parts[2]);
                int rt = parseRegister(parts[3]);

                reg["$" + std::to_string(rd)] = reg["$" + std::to_string(rs)] + reg["$" + std::to_string(rt)];
                counts["ALU"]++;
                PC += 1;
            }
            else if (opcodeStr == "addi") {
                // I-type ALU instruction
                int rt = parseRegister(parts[1]);
                int rs = parseRegister(parts[2]);
                int imm;
                imm = parseImmediate(parts[3], dataSymbolTable);
                reg["$" + std::to_string(rt)] = reg["$" + std::to_string(rs)] + imm;
                counts["ALU"]++;
                PC += 1;
            }
            else if (opcodeStr == "sub") {
                // R-type ALU instruction
                int rd = parseRegister(parts[1]);
                int rs = parseRegister(parts[2]);
                int rt = parseRegister(parts[3]);

                reg["$" + std::to_string(rd)] = reg["$" + std::to_string(rs)] - reg["$" + std::to_string(rt)];
                counts["ALU"]++;
                PC += 1;
            }
            else if (opcodeStr == "and") {
                // R-type ALU instruction
                int rd = parseRegister(parts[1]);
                int rs = parseRegister(parts[2]);
                int rt = parseRegister(parts[3]);

                reg["$" + std::to_string(rd)] = reg["$" + std::to_string(rs)] & reg["$" + std::to_string(rt)];
                counts["ALU"]++;
                PC += 1;
            }
            else if (opcodeStr == "or") {
                // R-type ALU instruction
                int rd = parseRegister(parts[1]);
                int rs = parseRegister(parts[2]);
                int rt = parseRegister(parts[3]);

                reg["$" + std::to_string(rd)] = reg["$" + std::to_string(rs)] | reg["$" + std::to_string(rt)];
                counts["ALU"]++;
                PC += 1;
            }
            else if (opcodeStr == "slt") {
                // R-type ALU instruction
                int rd = parseRegister(parts[1]);
                int rs = parseRegister(parts[2]);
                int rt = parseRegister(parts[3]);

                reg["$" + std::to_string(rd)] = (reg["$" + std::to_string(rs)] < reg["$" + std::to_string(rt)]) ? 1 : 0;
                counts["ALU"]++;
                PC += 1;
            }
            else if (opcodeStr == "lw") {
                // Load word
                int rt = parseRegister(parts[1]);
                size_t start = parts[2].find('(');
                size_t end = parts[2].find(')');
                int base = 0, offset = 0;
                if (start != std::string::npos && end != std::string::npos) {
                    std::string offsetStr = parts[2].substr(0, start);
                    std::string baseRegStr = parts[2].substr(start + 1, end - start - 1);
                    base = reg["$" + std::to_string(parseRegister(baseRegStr))];
                    offset = parseImmediate(offsetStr, dataSymbolTable);
                } else {
                    offset = parseImmediate(parts[2], dataSymbolTable);
                    base = 0;
                }
                int mem_address = base + offset;
                if (memory.count(mem_address)) {
                    reg["$" + std::to_string(rt)] = memory[mem_address];
                } else {
                    reg["$" + std::to_string(rt)] = 0;
                }
                counts["Memory"]++;
                PC += 1;
            }
            else if (opcodeStr == "sw") {
                // Store word
                int rt = parseRegister(parts[1]);
                size_t start = parts[2].find('(');
                size_t end = parts[2].find(')');
                int base = 0, offset = 0;
                if (start != std::string::npos && end != std::string::npos) {
                    std::string offsetStr = parts[2].substr(0, start);
                    std::string baseRegStr = parts[2].substr(start + 1, end - start - 1);
                    base = reg["$" + std::to_string(parseRegister(baseRegStr))];
                    offset = parseImmediate(offsetStr, dataSymbolTable);
                } else {
                    offset = parseImmediate(parts[2], dataSymbolTable);
                    base = 0;
                }
                int mem_address = base + offset;
                memory[mem_address] = reg["$" + std::to_string(rt)];
                counts["Memory"]++;
                PC += 1;
            }
            else if (opcodeStr == "j") {
                // Jump instruction
                std::string label = parts[1];
                if (labelAddresses.count(label)) {
                    PC = labelAddresses.at(label);
                } else {
                    std::cerr << "Undefined label: " << label << "\n";
                    exit(1);
                }
                counts["Jump"]++;
            }
            else if (opcodeStr == "beq") {
                // Branch if equal
                int rs = parseRegister(parts[1]);
                int rt = parseRegister(parts[2]);
                std::string label = parts[3];
                if (reg["$" + std::to_string(rs)] == reg["$" + std::to_string(rt)]) {
                    if (labelAddresses.count(label)) {
                        PC = labelAddresses.at(label);
                    } else {
                        std::cerr << "Undefined label: " << label << "\n";
                        exit(1);
                    }
                } else {
                    PC += 1;
                }
                counts["Branch"]++;
            }
            else if (opcodeStr == "bne") {
                // Branch if not equal
                int rs = parseRegister(parts[1]);
                int rt = parseRegister(parts[2]);
                std::string label = parts[3];
                if (reg["$" + std::to_string(rs)] != reg["$" + std::to_string(rt)]) {
                    if (labelAddresses.count(label)) {
                        PC = labelAddresses.at(label);
                    } else {
                        std::cerr << "Undefined label: " << label << "\n";
                        exit(1);
                    }
                } else {
                    PC += 1;
                }
                counts["Branch"]++;
            }
            else if (opcodeStr == "sll") {
                // Shift left logical
                int rd = parseRegister(parts[1]);
                int rt = parseRegister(parts[2]);
                int shamt = parseImmediate(parts[3], dataSymbolTable);

                reg["$" + std::to_string(rd)] = reg["$" + std::to_string(rt)] << shamt;
                counts["ALU"]++;
                PC += 1;
            }
            else if (opcodeStr == "srl") {
                // Shift right logical
                int rd = parseRegister(parts[1]);
                int rt = parseRegister(parts[2]);
                int shamt = parseImmediate(parts[3], dataSymbolTable);

                reg["$" + std::to_string(rd)] = static_cast<unsigned int>(reg["$" + std::to_string(rt)]) >> shamt;
                counts["ALU"]++;
                PC += 1;
            }
            else {
                // Handle other instructions similarly
                std::cerr << "Unsupported instruction during simulation: " << opcodeStr << "\n";
                exit(1);
            }

            // Ensure $zero register stays zero
            reg["$0"] = 0;

        } catch (const std::exception& e) {
            std::cerr << "Error during instruction execution: " << e.what() << "\n";
            exit(1);
        }

        if (single_step) {
            std::cout << "PC after execution: " << PC << "\n";
            printRegisters(reg);
            std::unordered_map<int, int> non_zero_memory;
            for (const auto& [addr, val] : memory) {
                if (val != 0) {
                    non_zero_memory[addr] = val;
                }
            }
            if (!non_zero_memory.empty()) {
                std::cout << "Updated Memory:\n";
                for (const auto& [addr, val] : non_zero_memory) {
                    std::cout << "M[" << addr << "]: " << val << "\n";
                }
            } else {
                std::cout << "No changes in memory.\n";
            }
            std::cout << std::string(80, '=') << "\n";

            std::cout << "\nPress 'n' to execute the next instruction, 'a' to switch to automatic mode: ";
            char cont;
            std::cin >> cont;
            if (cont == 'a') {
                single_step = false;
            }
        }

        counts["Total"]++;
    }

    std::cout << "\nRegister Values After Simulation:\n";
    printRegisters(reg);

    std::cout << "\nMemory Values After Simulation:\n";
    printMemory(memory);

    std::cout << "\nInstruction Counts:\n";
    for (const auto& [key, value] : counts) {
        std::cout << key << ": " << value << "\n";
    }
}

int main() {
    // Update the file path if necessary
    std::ifstream infile("C:/Users/91798/Mips_simulator/program.asm");
    if (!infile) {
        std::cerr << "Error opening file 'C:/Users/91798/Mips_simulator/program.asm'.\n";
        return 1;
    }

    std::vector<std::string> asmList;
    std::string line;
    int lineNumber = 0;
    std::unordered_map<std::string, int> labelAddresses;
    std::unordered_map<int, std::string> addressLabelMap;  // For reverse lookup during simulation

    // Variables for data handling
    Section currentSection = UNKNOWN;
    std::unordered_map<std::string, DataItem> dataSymbolTable;
    int dataAddress = 0x10010000; // Starting address of data segment
    std::unordered_map<int, int> memory; // Simulated memory

    while (std::getline(infile, line)) {
        std::string processedLine = preprocessLine(line, currentSection);
        if (processedLine.empty()) {
            continue;
        }

        // Remove commas and split the line
        std::string line = processedLine;
        line.erase(std::remove(line.begin(), line.end(), ','), line.end());
        std::istringstream iss(line);
        std::vector<std::string> parts{std::istream_iterator<std::string>{iss},
                                       std::istream_iterator<std::string>{}};
        if (parts.empty()) {
            continue;
        }

        if (currentSection == DATA) {
            // Handle data declarations

            // Check for label
            if (parts[0].back() == ':') {
                std::string label = parts[0].substr(0, parts[0].length() - 1);
                parts.erase(parts.begin());
                if (parts.empty()) {
                    // Next line contains the directive
                    if (!std::getline(infile, line)) {
                        std::cerr << "Unexpected end of file.\n";
                        return 1;
                    }
                    processedLine = preprocessLine(line, currentSection);
                    line = processedLine;
                    line.erase(std::remove(line.begin(), line.end(), ','), line.end());
                    iss.clear();
                    iss.str(line);
                    parts = {std::istream_iterator<std::string>{iss},
                             std::istream_iterator<std::string>{}};
                    if (parts.empty()) {
                        std::cerr << "Expected data directive after label.\n";
                        return 1;
                    }
                }
                std::string directive = parts[0];
                if (directive == ".word") {
                    parts.erase(parts.begin());
                    std::vector<int> values;
                    for (const auto& valStr : parts) {
                        int val = parseImmediate(valStr, dataSymbolTable);
                        values.push_back(val);
                    }
                    DataItem item;
                    item.address = dataAddress;
                    item.values = values;
                    dataSymbolTable[label] = item;
                    dataAddress += static_cast<int>(values.size() * 4); // Each word is 4 bytes
                }
                else if (directive == ".space") {
                    parts.erase(parts.begin());
                    int size = parseImmediate(parts[0], dataSymbolTable);
                    DataItem item;
                    item.address = dataAddress;
                    int numWords = (size + 3) / 4; // Round up to the next word
                    item.values.resize(numWords, 0);
                    dataSymbolTable[label] = item;
                    dataAddress += numWords * 4;
                }
                else if (directive == ".ascii" || directive == ".asciiz") {
                    parts.erase(parts.begin());
                    std::string str = line.substr(line.find('"') + 1);
                    str = str.substr(0, str.rfind('"'));
                    DataItem item;
                    item.address = dataAddress;
                    for (char c : str) {
                        item.values.push_back(static_cast<int>(c));
                        dataAddress += 1;
                    }
                    if (directive == ".asciiz") {
                        item.values.push_back(0); // Null terminator
                        dataAddress += 1;
                    }
                    dataSymbolTable[label] = item;
                    // Align dataAddress to next word if necessary
                    if (dataAddress % 4 != 0) {
                        dataAddress += (4 - (dataAddress % 4));
                    }
                }
                else {
                    std::cerr << "Unsupported data directive: " << directive << "\n";
                    return 1;
                }
            } else {
                std::cerr << "Expected label in .data section.\n";
                return 1;
            }
        } else if (currentSection == TEXT) {
            // Handle text (instructions)
            // Store label addresses
            if (!parts.empty() && parts[0].back() == ':') {
                std::string label = parts[0].substr(0, parts[0].length() - 1);
                labelAddresses[label] = lineNumber;
                addressLabelMap[lineNumber] = label;
                // Remove label from parts
                parts.erase(parts.begin());
                if (parts.empty()) {
                    // The line is just a label
                    asmList.push_back(""); // Placeholder for label-only line
                    lineNumber++;
                    continue;
                }
                // Reconstruct the line without the label
                std::ostringstream oss;
                std::copy(parts.begin(), parts.end(), std::ostream_iterator<std::string>(oss, " "));
                processedLine = oss.str();
            }
            asmList.push_back(processedLine);
            lineNumber++;
        }
        // Else ignore or error
    }
    infile.close();

    // Initialize memory with data
    for (const auto& [label, item] : dataSymbolTable) {
        int addr = item.address;
        for (int value : item.values) {
            memory[addr] = value;
            addr += 4; // Assuming word-aligned data
        }
    }

    // Opcode and function code mappings, instruction types
    std::unordered_map<std::string, int> opcodes = {
        {"lw", 35}, {"sw", 43}, {"beq", 4}, {"bne", 5}, {"addi", 8}, {"andi", 12}, {"ori", 13},
        {"slti", 10}, {"lui", 15}, {"j", 2}, {"jal", 3}
        // Add other opcodes as needed
    };

    std::unordered_map<std::string, int> functCodes = {
        {"add", 32}, {"sub", 34}, {"and", 36}, {"or", 37}, {"slt", 42},
        {"sll", 0}, {"srl", 2}, {"jr", 8}, {"jalr", 9}
        // Add other function codes as needed
    };

    std::unordered_map<std::string, std::string> instructionTypes = {
        {"add", "R"}, {"sub", "R"}, {"and", "R"}, {"or", "R"}, {"slt", "R"},
        {"sll", "R"}, {"srl", "R"}, {"jr", "R"}, {"jalr", "R"},
        {"addi", "I"}, {"andi", "I"}, {"ori", "I"}, {"slti", "I"},
        {"lw", "I"}, {"sw", "I"}, {"beq", "I"}, {"bne", "I"}, {"lui", "I"},
        {"j", "J"}, {"jal", "J"}
        // Add other instruction types as needed
    };

    // Assemble instructions into binary code
    std::vector<std::string> newAsmList;
    std::vector<std::string> binList;
    for (size_t i = 0; i < asmList.size(); ++i) {
        std::vector<std::string> binCodes = assembleInstruction(asmList[i], static_cast<int>(i), labelAddresses,
            opcodes, functCodes, instructionTypes, dataSymbolTable);
        for (size_t j = 0; j < binCodes.size(); ++j) {
            binList.push_back(binCodes[j]);
            newAsmList.push_back(asmList[i]); // Synchronize asmList and binList
        }
    }

    // Print assembly instructions and their binary code
    std::cout << "Assembly Instructions and Corresponding Binary Codes:\n";
    for (size_t i = 0; i < binList.size(); ++i) {
        if (!binList[i].empty()) {
            std::cout << newAsmList[i] << "\nBinary: " << binList[i] << "\n\n";
        }
    }

    // Simulate the execution of the instructions
    simulate(newAsmList, binList, labelAddresses, dataSymbolTable, memory);

    return 0;
}