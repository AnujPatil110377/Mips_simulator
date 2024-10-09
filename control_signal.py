import re

reg_map = {
    'zero': 0, 'at': 1,
    'v0': 2,  'v1': 3,
    'a0': 4,  'a1': 5,  'a2': 6,  'a3': 7,
    't0': 8,  't1': 9,  't2': 10, 't3': 11, 't4': 12,
    't5': 13, 't6': 14, 't7': 15,
    's0': 16, 's1':17,  's2':18,  's3':19,
    's4':20,  's5':21,  's6':22,  's7':23,
    't8':24,  't9':25,  'k0':26,  'k1':27,
    'gp':28,  'sp':29,  'fp':30,  'ra':31
}

def get_register_number(reg_name):
    reg_name = reg_name.strip().lstrip('$')
    if reg_name.isdigit():  # For registers like $0 - $31
        return int(reg_name)
    elif reg_name in reg_map:
        return reg_map[reg_name]
    else:
        raise ValueError(f"Unknown register name {reg_name}")

def get_register_name(num):
    for name, n in reg_map.items():
        if n == num:
            return name
    raise ValueError(f"Unknown register number {num}")

def read_asm_file(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()
    # Remove comments and empty lines
    instructions = []
    for line in lines:
        line = re.sub(r'#.*', '', line).strip()
        if line:
            instructions.append(line)
    return instructions

def parse_labels_and_instructions(instructions):
    labels = {}
    parsed_instructions = []
    pc = 0
    data_mode = False
    memory = {}
    current_address = 0x10010000  # Starting address for data section

    for line in instructions:
        if line.startswith(".data"):
            data_mode = True
            continue
        elif line.startswith(".text"):
            data_mode = False
            pc = 0
            continue

        if data_mode:
            if ':' in line:
                label, line_part = line.split(':', 1)
                labels[label.strip()] = current_address
                line = line_part.strip()
            if line.startswith('.word'):
                line = line.replace('.word', '').strip()
                values = line.split(',')
                for value in values:
                    memory[current_address] = int(value)
                    current_address += 4
            elif line.startswith('.asciiz'):
                line = line.replace('.asciiz', '').strip().strip('"')
                for char in line:
                    memory[current_address] = ord(char)
                    current_address += 1
                memory[current_address] = 0  # Null-terminate the string
                current_address += 1
        else:
            if ':' in line:
                label, line_part = line.split(':', 1)
                labels[label.strip()] = pc
                line = line_part.strip()
            if line:
                parsed_instructions.append(line)
                pc += 4
    return parsed_instructions, labels, memory

def convert_to_binary(instruction, labels, current_pc):
    opcodes = {
        "addi": "001000",
        "andi": "001100",
        "ori": "001101",
        "beq": "000100",
        "bne": "000101",
        "j": "000010",
        "jal": "000011",
        "lw": "100011",
        "sw": "101011",
        "lui": "001111",
        "and": "000000",
        "or": "000000",
        "slt": "000000",
        "add": "000000",
        "sub": "000000",
        "mul": "011100",  # Special MIPS opcode for multiplication
        "sll": "000000",
        "srl": "000000",
        "jr": "000000",
        "xor": "000000",
        "nor": "000000",
        "syscall": "000000",
    }
    functs = {
        "and": "100100",
        "or": "100101",
        "slt": "101010",
        "add": "100000",
        "sub": "100010",
        "mul": "000010",    # Function code for mul
        "sll": "000000",
        "srl": "000010",
        "jr": "001000",
        "xor": "100110",
        "nor": "100111",
        "syscall": "001100"
    }

    parts = re.split(r'[,\s()]+', instruction)
    parts = [p for p in parts if p]  # Remove empty strings
    op = parts[0]

    try:
        if op == "li":
            rd_num = get_register_number(parts[1])
            imm_value = int(parts[2])
            if -32768 <= imm_value <= 65535:
                # Use addi with $zero
                rs = format(0, '05b')  # $zero register
                rd = format(rd_num, '05b')
                imm = format(imm_value & 0xFFFF, '016b')
                return f"{opcodes['addi']}{rs}{rd}{imm}"
            else:
                # For larger immediates, need lui and ori
                # First instruction: lui rd, upper 16 bits
                upper = (imm_value >> 16) & 0xFFFF
                lower = imm_value & 0xFFFF
                rd = format(rd_num, '05b')
                rs = format(0, '05b')
                lui_inst = f"{opcodes['lui']}{rs}{rd}{format(upper, '016b')}"
                # Second instruction: ori rd, rd, lower 16 bits
                ori_inst = f"{opcodes['ori']}{rd}{rd}{format(lower, '016b')}"
                return [lui_inst, ori_inst]
        elif op == "la":
            rd_num = get_register_number(parts[1])
            label_address = labels.get(parts[2], 0)
            upper = (label_address >> 16) & 0xFFFF
            lower = label_address & 0xFFFF
            rd = format(rd_num, '05b')
            rs = format(0, '05b')
            lui_inst = f"{opcodes['lui']}{rs}{rd}{format(upper, '016b')}"
            ori_inst = f"{opcodes['ori']}{rd}{rd}{format(lower, '016b')}"
            return [lui_inst, ori_inst]
        elif op == "syscall":
            return f"{opcodes[op]}00000000000000000000{functs[op]}"
        elif op in ["addi", "andi", "ori"]:
            rt_num = get_register_number(parts[1])
            rs_num = get_register_number(parts[2])
            imm = int(parts[3])
            rs = format(rs_num, '05b')
            rt = format(rt_num, '05b')
            imm = format(imm & 0xFFFF, '016b')
            return f"{opcodes[op]}{rs}{rt}{imm}"
        elif op in ["lw", "sw"]:
            rt_num = get_register_number(parts[1])
            if len(parts) == 4:
                # Format: lw $rt, offset($rs)
                offset = int(parts[2])
                base_num = get_register_number(parts[3])
                rs = format(base_num, '05b')
                rt = format(rt_num, '05b')
                imm = format(offset & 0xFFFF, '016b')
                return f"{opcodes[op]}{rs}{rt}{imm}"
            elif len(parts) == 3:
                # Format: lw $rt, label
                address = labels.get(parts[2])
                if address is None:
                    raise ValueError(f"Label {parts[2]} not found")
                rs = format(0, '05b')  # Using $zero as base
                rt = format(rt_num, '05b')
                imm = format(address & 0xFFFF, '016b')
                return f"{opcodes[op]}{rs}{rt}{imm}"
            else:
                raise ValueError("Invalid lw/sw instruction format")
        elif op in ["beq", "bne"]:
            rs_num = get_register_number(parts[1])
            rt_num = get_register_number(parts[2])
            label = parts[3]
            if label in labels:
                offset = ((labels[label] - (current_pc + 4)) >> 2)
                imm = format(offset & 0xFFFF, '016b')
            else:
                imm = "0000000000000000"
            rs = format(rs_num, '05b')
            rt = format(rt_num, '05b')
            return f"{opcodes[op]}{rs}{rt}{imm}"
        elif op == "j" or op == "jal":
            label = parts[1]
            if label in labels:
                address = labels[label] >> 2
                return f"{opcodes[op]}{format(address, '026b')}"
            else:
                return None
        elif op in ["sll", "srl"]:
            rd_num = get_register_number(parts[1])
            rt_num = get_register_number(parts[2])
            shamt = int(parts[3])
            rs = format(0, '05b')
            rt = format(rt_num, '05b')
            rd = format(rd_num, '05b')
            shamt = format(shamt & 0x1F, '05b')
            funct = functs[op]
            return f"{opcodes[op]}{rs}{rt}{rd}{shamt}{funct}"
        elif op == "jr":
            rs_num = get_register_number(parts[1])
            rs = format(rs_num, '05b')
            rt = "00000"
            rd = "00000"
            shamt = "00000"
            funct = functs[op]
            return f"{opcodes[op]}{rs}{rt}{rd}{shamt}{funct}"
        elif op == "mul":
            rd_num = get_register_number(parts[1])
            rs_num = get_register_number(parts[2])
            rt_num = get_register_number(parts[3])
            rs = format(rs_num, '05b')
            rt = format(rt_num, '05b')
            rd = format(rd_num, '05b')
            shamt = "00000"
            funct = functs[op]
            return f"{opcodes[op]}{rs}{rt}{rd}{shamt}{funct}"
        else:
            # R-type instructions (add, sub, and, or, slt, etc.)
            rd_num = get_register_number(parts[1])
            rs_num = get_register_number(parts[2])
            rt_num = get_register_number(parts[3])
            rs = format(rs_num, '05b')
            rt = format(rt_num, '05b')
            rd = format(rd_num, '05b')
            shamt = "00000"
            funct = functs[op]
            return f"{opcodes[op]}{rs}{rt}{rd}{shamt}{funct}"
    except Exception as e:
        print(f"Error converting instruction: {instruction} -> {e}")
        return None

def generate_control_signals(op_code):
    signals = {
        'RegDst': 0,
        'RegWrite': 0,
        'ALUSrc': 0,
        'ALUOp': '00',
        'MemRead': 0,
        'MemWrite': 0,
        'MemtoReg': 0,
        'Branch': 0,
        'Jump': 0,
        'Syscall': 0  # Added syscall control signal
    }
    if op_code in ['add', 'sub', 'and', 'or', 'slt', 'mul', 'xor', 'nor', 'sll', 'srl']:
        signals['RegDst'] = 1
        signals['RegWrite'] = 1
        signals['ALUOp'] = '10'
    elif op_code in ['addi', 'andi', 'ori', 'li', 'lui']:
        signals['ALUSrc'] = 1
        signals['RegWrite'] = 1
        signals['ALUOp'] = '00'
    elif op_code == 'lw':
        signals['ALUSrc'] = 1
        signals['MemtoReg'] = 1
        signals['RegWrite'] = 1
        signals['MemRead'] = 1
        signals['ALUOp'] = '00'
    elif op_code == 'sw':
        signals['ALUSrc'] = 1
        signals['MemWrite'] = 1
        signals['ALUOp'] = '00'
    elif op_code == 'beq':
        signals['Branch'] = 1
        signals['ALUOp'] = '01'
    elif op_code == 'bne':
        signals['Branch'] = 1
        signals['ALUOp'] = '01'
    elif op_code == 'j':
        signals['Jump'] = 1
    elif op_code == 'jal':
        signals['Jump'] = 1
        signals['RegWrite'] = 1
    elif op_code == 'jr':
        signals['Jump'] = 1
    elif op_code == 'syscall':
        signals['Syscall'] = 1  # Indicate syscall operation
    else:
        # Unknown operation
        raise ValueError(f"Unsupported operation {op_code}")
    return signals

def display_registers(reg):
    print("Registers:")
    for i in range(0, 32, 4):
        reg_names = []
        for num in range(i, i+4):
            name = get_register_name(num)
            reg_names.append(name)
        print(f"${reg_names[0]:<3}: {reg[reg_names[0]]:10} | "
              f"${reg_names[1]:<3}: {reg[reg_names[1]]:10} | "
              f"${reg_names[2]:<3}: {reg[reg_names[2]]:10} | "
              f"${reg_names[3]:<3}: {reg[reg_names[3]]:10}")
    print()

def display_memory(memory):
    print("Memory:")
    addresses = sorted(memory.keys())
    for addr in addresses:
        value = memory[addr]
        if 32 <= value <= 126:
            display_value = f"{value} ('{chr(value)}')"
        else:
            display_value = str(value)
        print(f"Address {addr:08x}: {display_value}")
    print()

def syscall(reg, memory):
    syscall_num = reg['v0']
    if syscall_num == 1:
        # Print integer in $a0
        print(f"Output (int): {reg['a0']}")
    elif syscall_num == 4:
        # Print string at address in $a0
        print("Output (string):", end="")
        string_address = reg['a0']
        while memory.get(string_address, 0) != 0:
            print(chr(memory[string_address]), end="")
            string_address +=1
        print()
    elif syscall_num ==10:
        # Exit program
        print("Exiting program.")
        return False
    else:
        print(f"Unknown syscall: {syscall_num}")
    return True

def run_simulation(parsed_instructions, labels, memory):
    reg = {name: 0 for name in reg_map}
    reg['zero'] = 0  # Ensure $zero is always 0
    reg['sp'] = 0x7FFFFFFC  # Initialize $sp (Stack Pointer)
    pc = 0
    sim_mode = input("Enter 'n' for single instruction mode, 'a' for automatic mode: ")
    single_step = (sim_mode == 'n')

    # Prepare the instructions in order including expanded instructions for 'li' and 'la'
    instructions_list = []
    pc_counter = 0
    for inst in parsed_instructions:
        bin_inst = convert_to_binary(inst, labels, pc_counter)
        if bin_inst:
            if isinstance(bin_inst, list):
                # For 'li' and 'la' that expand into multiple instructions
                for bi in bin_inst:
                    instructions_list.append((inst, bi, pc_counter))
                    pc_counter += 4
            else:
                instructions_list.append((inst, bin_inst, pc_counter))
                pc_counter += 4
        else:
            instructions_list.append((inst, None, pc_counter))
            pc_counter += 4

    # Convert the instructions_list to a dictionary for easy PC lookup
    inD = {pc: (inst, mc) for inst, mc, pc in instructions_list}
    with open("binary_code.txt", "w") as bin_file:
        while pc in inD:
            current_instruction, mc = inD[pc]
            parts = re.split(r'[,\s()]+', current_instruction)
            parts = [p for p in parts if p]  # Remove empty strings
            op_code = parts[0]

            # Generate control signals
            try:
                control_signals = generate_control_signals(op_code)
            except ValueError as e:
                print(f"Error: {e}")
                break

            if single_step:
                print("\n" + "=" * 80)
                print("Executing Instruction:")
                print("Assembly Code:", current_instruction)
                if mc:
                    print("Machine Code:", mc)
                else:
                    print("Machine Code: N/A")
                print("PC before execution:", pc)
                print("Control Signals:", control_signals)

            if mc:
                if isinstance(mc, list):
                    for instruction in mc:
                        bin_file.write(f"{instruction}\n")
                else:
                    bin_file.write(f"{mc}\n")

            try:
                # Handle syscall separately
                if op_code == 'syscall':
                    if not syscall(reg, memory):
                        break
                elif control_signals['Jump']:
                    if op_code == 'j' or op_code == 'jal':
                        label = parts[1]
                        if label in labels:
                            if op_code == 'jal':
                                reg['ra'] = pc + 4  # Save return address
                            pc = labels[label]
                            continue
                        else:
                            raise ValueError(f"Label {label} not found")
                    elif op_code == 'jr':
                        rs_name = get_register_name(get_register_number(parts[1]))
                        pc = reg[rs_name]
                        continue
                elif control_signals['Branch']:
                    rs_name = get_register_name(get_register_number(parts[1]))
                    rt_name = get_register_name(get_register_number(parts[2]))
                    label = parts[3]
                    if op_code == 'beq' and reg[rs_name] == reg[rt_name]:
                        pc = labels[label]
                        continue
                    elif op_code == 'bne' and reg[rs_name] != reg[rt_name]:
                        pc = labels[label]
                        continue
                else:
                    ALU_result = 0
                    if control_signals['ALUSrc']:
                        if op_code in ['addi', 'andi', 'ori']:
                            rt_name = get_register_name(get_register_number(parts[1]))
                            rs_name = get_register_name(get_register_number(parts[2]))
                            imm = int(parts[3])
                            if op_code == 'addi':
                                ALU_result = reg[rs_name] + imm
                            elif op_code == 'andi':
                                ALU_result = reg[rs_name] & imm
                            elif op_code == 'ori':
                                ALU_result = reg[rs_name] | imm
                            if control_signals['RegWrite']:
                                reg[rt_name] = ALU_result
                        elif op_code == 'lui':
                            rt_name = get_register_name(get_register_number(parts[1]))
                            imm = int(parts[2])
                            if control_signals['RegWrite']:
                                reg[rt_name] = imm << 16
                        elif op_code == 'li':
                            rd_name = get_register_name(get_register_number(parts[1]))
                            imm = int(parts[2])
                            if control_signals['RegWrite']:
                                reg[rd_name] = imm
                        elif op_code == 'lw':
                            rt_name = get_register_name(get_register_number(parts[1]))
                            if len(parts) == 4:
                                offset = int(parts[2])
                                base_name = get_register_name(get_register_number(parts[3]))
                                address = reg[base_name] + offset
                            elif len(parts) == 3:
                                # lw rt, label
                                label = parts[2]
                                address = labels.get(label)
                                if address is None:
                                    raise ValueError(f"Label {label} not found")
                            else:
                                raise ValueError("Invalid lw instruction format")
                            if control_signals['MemRead']:
                                data = memory.get(address, 0)
                                if control_signals['RegWrite']:
                                    reg[rt_name] = data
                        elif op_code == 'sw':
                            rt_name = get_register_name(get_register_number(parts[1]))
                            if len(parts) == 4:
                                offset = int(parts[2])
                                base_name = get_register_name(get_register_number(parts[3]))
                                address = reg[base_name] + offset
                            elif len(parts) == 3:
                                label = parts[2]
                                address = labels.get(label)
                                if address is None:
                                    raise ValueError(f"Label {label} not found")
                            else:
                                raise ValueError("Invalid sw instruction format")
                            if control_signals['MemWrite']:
                                memory[address] = reg[rt_name]
                    else:
                        # ALU operations with register operands
                        rd_name = get_register_name(get_register_number(parts[1]))
                        rs_name = get_register_name(get_register_number(parts[2]))
                        rt_name = get_register_name(get_register_number(parts[3]))
                        if op_code == 'add':
                            ALU_result = reg[rs_name] + reg[rt_name]
                        elif op_code == 'sub':
                            ALU_result = reg[rs_name] - reg[rt_name]
                        elif op_code == 'and':
                            ALU_result = reg[rs_name] & reg[rt_name]
                        elif op_code == 'or':
                            ALU_result = reg[rs_name] | reg[rt_name]
                        elif op_code == 'slt':
                            ALU_result = 1 if reg[rs_name] < reg[rt_name] else 0
                        elif op_code == 'mul':
                            ALU_result = reg[rs_name] * reg[rt_name]
                        elif op_code == 'xor':
                            ALU_result = reg[rs_name] ^ reg[rt_name]
                        elif op_code == 'nor':
                            ALU_result = ~(reg[rs_name] | reg[rt_name])
                        elif op_code == 'sll':
                            rt_name = get_register_name(get_register_number(parts[2]))
                            shamt = int(parts[3])
                            ALU_result = reg[rt_name] << shamt
                        elif op_code == 'srl':
                            rt_name = get_register_name(get_register_number(parts[2]))
                            shamt = int(parts[3])
                            ALU_result = reg[rt_name] >> shamt
                        else:
                            raise ValueError(f"Unsupported ALU operation {op_code}")
                        if control_signals['RegWrite']:
                            reg[rd_name] = ALU_result
            except Exception as e:
                print(f"Error executing instruction: {current_instruction} -> {e}")
                break

            if single_step:
                display_registers(reg)
                # Optionally display memory
                # display_memory(memory)
                print("PC after execution:", pc + 4)
                input("Press Enter to continue...")

            pc += 4

    if not single_step:
        display_registers(reg)
        # Optionally display memory if needed
        # display_memory(memory)

def main():
    file_path = "program.asm"  # Ensure this file exists with your assembly code
    instructions = read_asm_file(file_path)

    parsed_instructions, labels, memory = parse_labels_and_instructions(instructions)

    print("Assembly to Machine Code Conversion:")
    pc_counter = 0
    for inst in parsed_instructions:
        bin_inst = convert_to_binary(inst, labels, pc_counter)
        if bin_inst:
            if isinstance(bin_inst, list):
                for bi in bin_inst:
                    print(f"{inst} -> {bi}")
                    pc_counter += 4
            else:
                print(f"{inst} -> {bin_inst}")
                pc_counter += 4
        else:
            print(f"{inst} -> Invalid instruction")
            pc_counter += 4

    run_simulation(parsed_instructions, labels, memory)

if __name__ == "__main__":
    main()