import re

# Register mapping
reg_map = {
    'zero': 0, 'at': 1,
    'v0': 2,  'v1': 3,
    'a0': 4,  'a1': 5,  'a2': 6,  'a3': 7,
    't0': 8,  't1': 9,  't2': 10, 't3': 11, 't4': 12,
    't5': 13, 't6': 14, 't7': 15,
    's0': 16, 's1': 17, 's2': 18, 's3': 19,
    's4': 20, 's5': 21, 's6': 22, 's7': 23,
    't8': 24, 't9': 25, 'k0': 26, 'k1': 27,
    'gp': 28, 'sp': 29, 'fp': 30, 'ra': 31
}

# Reverse mapping for easy lookup
rev_reg_map = {v: k for k, v in reg_map.items()}

def get_register_number(reg_name):
    reg_name = reg_name.strip().lstrip('$')
    if reg_name.isdigit():  # For registers like $0 - $31
        num = int(reg_name)
        if 0 <= num <= 31:
            return num
        else:
            raise ValueError(f"Register number {num} out of range")
    elif reg_name in reg_map:
        return reg_map[reg_name]
    else:
        raise ValueError(f"Unknown register name {reg_name}")

def get_register_name(num):
    if num in rev_reg_map:
        return rev_reg_map[num]
    else:
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
                    memory[current_address] = int(value, 0)  # Support hex literals
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
    # Binary opcode mappings
    opcodes = {
        "addi": 0b001000,
        "andi": 0b001100,
        "ori":  0b001101,
        "beq":  0b000100,
        "bne":  0b000101,
        "j":    0b000010,
        "jal":  0b000011,
        "lw":   0b100011,
        "sw":   0b101011,
        "lui":  0b001111,
        "and":  0b000000,
        "or":   0b000000,
        "slt":  0b000000,
        "add":  0b000000,
        "sub":  0b000000,
        "mul":  0b011100,  # SPECIAL opcode for multiplication
        "sll":  0b000000,
        "srl":  0b000000,
        "jr":   0b000000,
        "xor":  0b000000,
        "nor":  0b000000,
        "syscall": 0b000000,
    }

    functs = {
        "and":    0b100100,
        "or":     0b100101,
        "slt":    0b101010,
        "add":    0b100000,
        "sub":    0b100010,
        "mul":    0b000010,    # Function code for mul
        "sll":    0b000000,
        "srl":    0b000010,
        "jr":     0b001000,
        "xor":    0b100110,
        "nor":    0b100111,
        "syscall":0b001100
    }

    parts = re.split(r'[,\s()]+', instruction)
    parts = [p for p in parts if p]  # Remove empty strings
    op = parts[0]

    try:
        if op == "li":
            rd_num = get_register_number(parts[1])
            imm_value = int(parts[2], 0)  # Supports hexadecimal
            if -32768 <= imm_value <= 65535:
                # Use addi with $zero
                rs = 0  # $zero register
                rt = rd_num
                imm = imm_value & 0xFFFF
                binary_inst = (opcodes['addi'] << 26) | (rs << 21) | (rt << 16) | imm
                return [binary_inst]
            else:
                # For larger immediates, need lui and ori
                upper = (imm_value >> 16) & 0xFFFF
                lower = imm_value & 0xFFFF
                rs = 0  # $zero register
                rd = rd_num
                lui_inst = (opcodes['lui'] << 26) | (rs << 21) | (rd << 16) | upper
                ori_inst = (opcodes['ori'] << 26) | (rd << 21) | (rd << 16) | lower
                return [lui_inst, ori_inst]
        elif op == "la":
            rd_num = get_register_number(parts[1])
            label_address = labels.get(parts[2], 0)
            upper = (label_address >> 16) & 0xFFFF
            lower = label_address & 0xFFFF
            rs = 0  # $zero register
            rd = rd_num
            lui_inst = (opcodes['lui'] << 26) | (rs << 21) | (rd << 16) | upper
            ori_inst = (opcodes['ori'] << 26) | (rd << 21) | (rd << 16) | lower
            return [lui_inst, ori_inst]
        elif op == "syscall":
            return (opcodes[op] << 26) | functs[op]
        elif op in ["addi", "andi", "ori"]:
            rt_num = get_register_number(parts[1])
            rs_num = get_register_number(parts[2])
            imm = int(parts[3], 0) & 0xFFFF
            binary_inst = (opcodes[op] << 26) | (rs_num << 21) | (rt_num << 16) | imm
            return binary_inst
        elif op in ["lw", "sw"]:
            rt_num = get_register_number(parts[1])
            if len(parts) == 4:
                # Format: lw $rt, offset($rs)
                offset = int(parts[2], 0)
                base_num = get_register_number(parts[3])
                binary_inst = (opcodes[op] << 26) | (base_num << 21) | (rt_num << 16) | (offset & 0xFFFF)
                return binary_inst
            elif len(parts) == 3:
                # Format: lw $rt, label
                address = labels.get(parts[2])
                if address is None:
                    raise ValueError(f"Label {parts[2]} not found")
                rs = 0  # Using $zero as base
                rt = rt_num
                imm = address & 0xFFFF
                binary_inst = (opcodes[op] << 26) | (rs << 21) | (rt << 16) | imm
                return binary_inst
            else:
                raise ValueError("Invalid lw/sw instruction format")
        elif op in ["beq", "bne"]:
            rs_num = get_register_number(parts[1])
            rt_num = get_register_number(parts[2])
            label = parts[3]
            if label in labels:
                offset = ((labels[label] - (current_pc + 4)) >> 2) & 0xFFFF
            else:
                offset = 0
            binary_inst = (opcodes[op] << 26) | (rs_num << 21) | (rt_num << 16) | offset
            return binary_inst
        elif op == "j" or op == "jal":
            label = parts[1]
            if label in labels:
                address = (labels[label] >> 2) & 0x3FFFFFF
                binary_inst = (opcodes[op] << 26) | address
                return binary_inst
            else:
                raise ValueError(f"Label {label} not found")
        elif op in ["sll", "srl"]:
            rd_num = get_register_number(parts[1])
            rt_num = get_register_number(parts[2])
            shamt = int(parts[3], 0) & 0x1F
            # For sll and srl, rs is zero
            binary_inst = (opcodes[op] << 26) | (0 << 21) | (rt_num << 16) | (rd_num << 11) | (shamt << 6) | functs[op]
            return binary_inst
        elif op == "jr":
            rs_num = get_register_number(parts[1])
            # For jr, funct specifies the operation and other fields are zero
            binary_inst = (opcodes[op] << 26) | (rs_num << 21) | functs[op]
            return binary_inst
        elif op == "mul":
            rd_num = get_register_number(parts[1])
            rs_num = get_register_number(parts[2])
            rt_num = get_register_number(parts[3])
            shamt = 0
            binary_inst = (opcodes[op] << 26) | (rs_num << 21) | (rt_num << 16) | (rd_num << 11) | (shamt << 6) | functs[op]
            return binary_inst
        else:
            # R-type instructions (add, sub, and, or, slt, etc.)
            if op not in functs:
                raise ValueError(f"Unsupported operation {op}")
            rd_num = get_register_number(parts[1])
            rs_num = get_register_number(parts[2])
            rt_num = get_register_number(parts[3])
            shamt = 0
            binary_inst = (opcodes[op] << 26) | (rs_num << 21) | (rt_num << 16) | (rd_num << 11) | (shamt << 6) | functs[op]
            return binary_inst
    except Exception as e:
        print(f"Error converting instruction: '{instruction}' -> {e}")
        return None

def generate_control_signals(op_code, funct_code=0):
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
    # Define R-type operations based on funct_code
    R_type_ops = {
        0b100000: 'add',
        0b100010: 'sub',
        0b100100: 'and',
        0b100101: 'or',
        0b101010: 'slt',
        0b011100: 'mul',
        0b000000: 'sll',
        0b000010: 'srl',  # Differentiated by opcode
        0b001000: 'jr',
        0b100110: 'xor',
        0b100111: 'nor',
        0b001100: 'syscall'
    }

    I_type_ops = ['addi', 'andi', 'ori', 'lui', 'lw', 'sw', 'beq', 'bne']
    J_type_ops = ['j', 'jal']
    syscall_ops = ['syscall']

    if op_code == 0b000000:
        # R-type
        op_name = R_type_ops.get(funct_code, 'unknown')
        if op_name in ['add', 'sub', 'and', 'or', 'slt', 'mul', 'xor', 'nor', 'sll', 'srl']:
            signals['RegDst'] = 1
            signals['RegWrite'] = 1
            signals['ALUOp'] = '10'
        elif op_name == 'jr':
            signals['Jump'] = 1
        elif op_name == 'syscall':
            signals['Syscall'] = 1
    elif op_code in [0b001000, 0b001100, 0b001101, 0b000100, 0b000101, 0b100011, 0b101011, 0b001111]:
        # I-type instructions
        if op_code in [0b001000, 0b001100, 0b001101]:  # addi, andi, ori
            signals['ALUSrc'] = 1
            signals['RegWrite'] = 1
            signals['ALUOp'] = '00'
            if op_code == 0b001111:  # lui
                signals['ALUOp'] = '11'
        elif op_code == 0b100011:  # lw
            signals['ALUSrc'] = 1
            signals['MemtoReg'] = 1
            signals['RegWrite'] = 1
            signals['MemRead'] = 1
            signals['ALUOp'] = '00'
        elif op_code == 0b101011:  # sw
            signals['ALUSrc'] = 1
            signals['MemWrite'] = 1
            signals['ALUOp'] = '00'
        elif op_code in [0b000100, 0b000101]:  # beq, bne
            signals['Branch'] = 1
            signals['ALUOp'] = '01'
    elif op_code in [0b000010, 0b000011]:  # j, jal
        signals['Jump'] = 1
        if op_code == 0b000011:  # jal
            signals['RegWrite'] = 1
    else:
        # Unknown operation
        raise ValueError(f"Unsupported opcode {op_code:06b}")

    return signals

def display_registers(reg):
    print("Registers:")
    for i in range(0, 32, 4):
        reg_names = [get_register_name(num) for num in range(i, i+4)]
        print(f"${reg_names[0]:<3}: {reg[reg_names[0]]:<10} | "
              f"${reg_names[1]:<3}: {reg[reg_names[1]]:<10} | "
              f"${reg_names[2]:<3}: {reg[reg_names[2]]:<10} | "
              f"${reg_names[3]:<3}: {reg[reg_names[3]]:<10}")
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

def syscall_handler(reg, memory):
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
            string_address += 1
        print()
    elif syscall_num == 10:
        # Exit program
        print("Exiting program.")
        return False
    else:
        print(f"Unknown syscall: {syscall_num}")
    return True

def Run_simulation(parsed_instructions, labels, memory):
    # Initialize registers
    reg = {name: 0 for name in reg_map}
    reg['zero'] = 0  # Ensure $zero is always 0
    reg['sp'] = 0x7FFFFFFC  # Initialize $sp (Stack Pointer)
    
    pc = 0
    sim_mode = input("Enter 'n' for single instruction mode, 'a' for automatic mode: ").strip().lower()
    single_step = (sim_mode == 'n')

    # Prepare the instructions in order including expanded instructions for 'li' and 'la'
    instructions_list = []
    pc_counter = 0
    binary_instructions = []
    for inst in parsed_instructions:
        bin_inst = convert_to_binary(inst, labels, pc_counter)
        if bin_inst:
            if isinstance(bin_inst, list):
                # For 'li' and 'la' that expand into multiple instructions
                for bi in bin_inst:
                    instructions_list.append((inst, bi, pc_counter))
                    binary_instructions.append(bi)
                    pc_counter += 4
            else:
                instructions_list.append((inst, bin_inst, pc_counter))
                binary_instructions.append(bin_inst)
                pc_counter += 4
        else:
            print(f"Invalid instruction at PC {pc_counter}: {inst}")
            binary_instructions.append(0)  # Placeholder for invalid instruction
            pc_counter += 4

    total_instructions = len(binary_instructions)

    with open("binary_code.txt", "w") as bin_file:
        while pc < total_instructions * 4:
            current_index = pc // 4
            current_instruction = binary_instructions[current_index]

            # Extract opcode
            op_code = (current_instruction >> 26) & 0b111111

            # Determine the operation name based on opcode
            opcode_map = {
                0b001000: "addi",
                0b001100: "andi",
                0b001101: "ori",
                0b000100: "beq",
                0b000101: "bne",
                0b000010: "j",
                0b000011: "jal",
                0b100011: "lw",
                0b101011: "sw",
                0b001111: "lui",
                0b011100: "mul",  # SPECIAL opcode for mul
                0b000000: "R-type",  # To be determined by funct
            }

            if op_code in opcode_map:
                op_name = opcode_map[op_code]
                if op_name == "R-type":
                    funct = current_instruction & 0b111111
                    funct_map = {
                        0b100000: "add",
                        0b100010: "sub",
                        0b100100: "and",
                        0b100101: "or",
                        0b101010: "slt",
                        0b011100: "mul",
                        0b000000: "sll",
                        0b000010: "srl",  # Differentiated by opcode
                        0b001000: "jr",
                        0b100110: "xor",
                        0b100111: "nor",
                        0b001100: "syscall"
                    }
                    op_name = funct_map.get(funct, "unknown")
            else:
                op_name = "unknown"

            # Generate control signals
            try:
                if op_name == "unknown":
                    raise ValueError(f"Unknown operation with opcode {op_code:06b}")
                control_signals = generate_control_signals(op_code, funct_code=(current_instruction & 0b111111))
            except ValueError as e:
                print(f"Error: {e}")
                break

            # Decode fields based on instruction type
            rs = (current_instruction >> 21) & 0b11111
            rt = (current_instruction >> 16) & 0b11111
            rd = (current_instruction >> 11) & 0b11111
            shamt = (current_instruction >> 6) & 0b11111
            funct = current_instruction & 0b111111
            immediate = current_instruction & 0xFFFF
            address = current_instruction & 0x3FFFFFF

            if single_step:
                print("\n" + "=" * 80)
                print("Executing Instruction:")
                print(f"PC: {pc:08x}")
                print(f"Instruction: {current_instruction:032b} ({op_name})")
                print("Control Signals:", control_signals)

            # Write machine code to file
            bin_file.write(f"{current_instruction:032b}\n")

            # Execute the instruction
            try:
                # Handle syscall separately
                if op_name == 'syscall':
                    if not syscall_handler(reg, memory):
                        break
                elif control_signals['Jump']:
                    if op_name == 'j' or op_name == 'jal':
                        target_address = (address << 2)  # Word aligned
                        if op_name == 'jal':
                            reg['ra'] = pc + 4  # Save return address
                        pc = target_address
                        continue
                    elif op_name == 'jr':
                        rs_name = get_register_name(rs)
                        pc = reg[rs_name]
                        continue
                elif control_signals['Branch']:
                    rs_name = get_register_name(rs)
                    rt_name = get_register_name(rt)
                    # Sign-extend immediate
                    imm = immediate if (immediate & 0x8000) == 0 else immediate - 0x10000
                    if op_name == 'beq' and reg[rs_name] == reg[rt_name]:
                        pc += (imm << 2)
                        continue
                    elif op_name == 'bne' and reg[rs_name] != reg[rt_name]:
                        pc += (imm << 2)
                        continue
                else:
                    # ALU operations
                    if control_signals['ALUSrc']:
                        if op_name in ['addi', 'andi', 'ori']:
                            rs_val = reg[get_register_name(rs)]
                            imm = immediate if (immediate & 0x8000) == 0 else immediate - 0x10000
                            if op_name == 'addi':
                                result = rs_val + imm
                            elif op_name == 'andi':
                                result = rs_val & imm
                            elif op_name == 'ori':
                                result = rs_val | imm
                            reg_name = get_register_name(rt)
                            if control_signals['RegWrite']:
                                reg[reg_name] = result & 0xFFFFFFFF  # Ensure 32-bit
                        elif op_name == 'lui':
                            imm = immediate
                            reg_name = get_register_name(rt)
                            if control_signals['RegWrite']:
                                reg[reg_name] = (imm << 16) & 0xFFFFFFFF
                        elif op_name == 'lw':
                            base = reg[get_register_name(rs)]
                            imm = immediate if (immediate & 0x8000) == 0 else immediate - 0x10000
                            address_calc = base + imm
                            data = memory.get(address_calc, 0)
                            reg_name = get_register_name(rt)
                            if control_signals['RegWrite']:
                                reg[reg_name] = data
                        elif op_name == 'sw':
                            base = reg[get_register_name(rs)]
                            imm = immediate if (immediate & 0x8000) == 0 else immediate - 0x10000
                            address_calc = base + imm
                            memory[address_calc] = reg[get_register_name(rt)]
                    else:
                        # R-type operations
                        rs_val = reg[get_register_name(rs)]
                        rt_val = reg[get_register_name(rt)]
                        if op_name == 'add':
                            result = rs_val + rt_val
                        elif op_name == 'sub':
                            result = rs_val - rt_val
                        elif op_name == 'and':
                            result = rs_val & rt_val
                        elif op_name == 'or':
                            result = rs_val | rt_val
                        elif op_name == 'slt':
                            result = 1 if rs_val < rt_val else 0
                        elif op_name == 'mul':
                            result = rs_val * rt_val
                        elif op_name == 'xor':
                            result = rs_val ^ rt_val
                        elif op_name == 'nor':
                            result = ~(rs_val | rt_val) & 0xFFFFFFFF
                        elif op_name == 'sll':
                            result = (rt_val << shamt) & 0xFFFFFFFF
                        elif op_name == 'srl':
                            result = (rt_val & 0xFFFFFFFF) >> shamt
                        else:
                            raise ValueError(f"Unsupported ALU operation {op_name}")
                        rd_name = get_register_name(rd)
                        if control_signals['RegWrite']:
                            reg[rd_name] = result
            except Exception as e:
                print(f"Error executing instruction at PC {pc}: {e}")
                break

            if single_step:
                display_registers(reg)
                # Optionally display memory
                # display_memory(memory)
                print(f"PC after execution: {pc + 4:08x}")
                input("Press Enter to continue...")

            pc += 4

def main():
    file_path = "program.asm"  # Ensure this file exists with your assembly code
    instructions = read_asm_file(file_path)

    parsed_instructions, labels, memory = parse_labels_and_instructions(instructions)

    print("Assembly to Machine Code Conversion:")
    pc_counter = 0
    binary_instructions = []
    for inst in parsed_instructions:
        bin_inst = convert_to_binary(inst, labels, pc_counter)
        if bin_inst:
            if isinstance(bin_inst, list):
                for bi in bin_inst:
                    print(f"{inst} -> {bi:032b}")
                    binary_instructions.append(bi)
                    pc_counter += 4
            else:
                print(f"{inst} -> {bin_inst:032b}")
                binary_instructions.append(bin_inst)
                pc_counter += 4
        else:
            print(f"{inst} -> Invalid instruction")
            binary_instructions.append(0)  # Placeholder for invalid instruction
            pc_counter += 4

    Run_simulation(parsed_instructions, labels, memory)

if __name__ == "__main__":
    main()