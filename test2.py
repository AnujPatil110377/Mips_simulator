import re

def read_asm_file(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()
    return [re.sub(r'#.*', '', line).strip() for line in lines if line.strip()]

def parse_labels_and_instructions(instructions):
    labels = {}
    parsed_instructions = []
    pc = 0
    for line in instructions:
        if ':' in line:
            label, line = line.split(':', 1)
            labels[label.strip()] = pc
            line = line.strip()
        if line:
            parsed_instructions.append(line)
            pc += 4
    return parsed_instructions, labels

def convert_to_binary(instruction, labels, current_pc):
    opcodes = {
        "addi": "001000",
        "beq": "000100",
        "bne": "000101",
        "j": "000010",
        "lw": "100011",
        "sw": "101011",
        "and": "000000",
        "sll": "000000",
        "srl": "000000",
        "sub": "000000",
        "slt": "000000",
        "add": "000000",
        "calc": "000000",
    }
    functs = {
        "and": "100100",
        "sll": "000000",
        "srl": "000010",
        "sub": "100010",
        "slt": "101010",
        "add": "100000",
        "calc": "111111",
    }

    parts = instruction.replace(",", "").split()
    op = parts[0]
    if op not in opcodes:
        return None

    try:
        if op in ["addi", "lw", "sw"]:
            rt = format(int(parts[1][1:]), '05b')
            rs = format(int(parts[2][1:]), '05b')
            imm = format(int(parts[3]) & 0xFFFF, '016b')
            return f"{opcodes[op]}{rs}{rt}{imm}"
        elif op in ["beq", "bne"]:
            rs = format(int(parts[1][1:]), '05b')
            rt = format(int(parts[2][1:]), '05b')
            label = parts[3]
            if label in labels:
                offset = ((labels[label] - (current_pc + 4)) >> 2)
                imm = format(offset & 0xFFFF, '016b')
            else:
                imm = "0000000000000000"
            return f"{opcodes[op]}{rs}{rt}{imm}"
        elif op == "j":
            label = parts[1]
            if label in labels:
                address = labels[label] >> 2
                return f"{opcodes[op]}{format(address, '026b')}"
            else:
                return None
        else:
            rd = format(int(parts[1][1:]), '05b')
            rs = format(int(parts[2][1:]), '05b')
            rt = format(int(parts[3][1:]), '05b') if op != "calc" else "00000"
            shamt = "00000"
            funct = functs[op]
            return f"{opcodes[op]}{rs}{rt}{rd}{shamt}{funct}"
    except:
        return None

def toAsm(mc, asm):
    op = {
        "001000": "addi",
        "000100": "beq",
        "000101": "bne",
        "000010": "j",
        "100011": "lw",
        "101011": "sw",
    }
    functs = {
        "100100": "and",
        '000000': 'sll',
        '000010': 'srl',
        '100010': 'sub',
        '101010': 'slt',
        "100000": 'add',
        "111111": "calc",
    }
    opcode = mc[:6]
    if opcode == '000000':
        rs = mc[6:11]
        rt = mc[11:16]
        rd = mc[16:21]
        shamt = mc[21:26]
        funct = mc[26:]
        if funct in functs:
            if funct == '000000' or funct == '000010':
                asm.append(f"{functs[funct]} ${int(rd, 2)}, ${int(rt, 2)}, {int(shamt, 2)}")
            elif funct == '111111':
                asm.append(f"{functs[funct]} ${int(rd, 2)}, ${int(rs, 2)}")
            else:
                asm.append(f"{functs[funct]} ${int(rd, 2)}, ${int(rs, 2)}, ${int(rt, 2)}")
    elif opcode in op:
        if opcode == '000010':
            address = int(mc[6:], 2) << 2
            asm.append(f"{op[opcode]} {address}")
        else:
            rs = mc[6:11]
            rt = mc[11:16]
            imm0 = mc[16:]
            imm = int(imm0, 2)
            if imm0[0] == '1':
                imm -= 1 << len(imm0)
            if opcode == '100011' or opcode == '101011':
                asm.append(f"{op[opcode]} ${int(rt, 2)}, {imm}(${int(rs, 2)})")
            else:
                asm.append(f"{op[opcode]} ${int(rt, 2)}, ${int(rs, 2)}, {imm}")

def print_registers(reg):
    print("Registers:")
    for i in range(0, 32, 4):
        print(f"${i:2}: {reg[f'${i}']:10} | ${i+1:2}: {reg[f'${i+1}']:10} | ${i+2:2}: {reg[f'${i+2}']:10} | ${i+3:2}: {reg[f'${i+3}']:10}")
    print()

def print_memory(memory):
    print("Memory:")
    non_zero_addresses = [address for address, value in memory.items() if value != 0]
    if not non_zero_addresses:
        print("\nAll memory values are 0.\n")
        return
    min_address = min(non_zero_addresses)
    max_address = max(non_zero_addresses)
    start_address = min_address - (min_address % 4)
    while max_address - start_address < 32 * 4:
        max_address += 4
    for address in range(start_address, max_address + 1, 16):
        for offset in range(0, 16, 4):
            current_address = address + offset
            value = memory.get(current_address, 0)
            print(f"M[{current_address:5}]: {value:10}", end=" | ")
        print()
    print()

def sim(inD, labels, reg, memory, binList):
    PC = 0
    counts = {
        'Total': 0,
        'ALU': 0,
        'Jump': 0,
        'Branch': 0,
        'Memory': 0,
        'Other': 0,
        'Special': 0
    }
    mode = input("Enter 'n' for single instruction mode, 'a' for automatic mode: ")
    single_step = True if mode == 'n' else False
    pc_to_mc = {pc: mc for pc, mc in zip(range(0, len(binList) * 4, 4), binList)}

    while PC in inD:
        curr = inD[PC]
        part = curr.replace(",", "").split(" ")
        if single_step:
            print("\n" + "=" * 80)
            print("Executing Instruction:")
            print("Assembly Code:", curr)
            mc = pc_to_mc.get(PC)
            if mc is not None:
                print("Machine Code:", mc)
            else:
                print("No machine code found for this PC.")
            print("PC before execution:", PC)

        if part[0] == 'addi':
            reg[part[1]] = reg[part[2]] + int(part[3])
            counts['ALU'] += 1
            PC += 4
        elif part[0] == 'beq':
            rs = reg[part[1]]
            rt = reg[part[2]]
            label = part[3]
            if rs == rt:
                PC = labels[label]
            else:
                PC += 4
            counts['Branch'] += 1
        elif part[0] == 'bne':
            rs = reg[part[1]]
            rt = reg[part[2]]
            label = part[3]
            if rs != rt:
                PC = labels[label]
            else:
                PC += 4
            counts['Branch'] += 1
        elif part[0] == 'j':
            label = part[1]
            if label in labels:
                PC = labels[label]
            counts['Jump'] += 1
        elif part[0] == 'lw':
            rt = part[1]
            imm, rs_reg = part[2].split('(')
            rs_reg = rs_reg[:-1]
            mem_address = reg[rs_reg] + int(imm)
            reg[rt] = memory.get(mem_address, 0)
            counts['Memory'] += 1
            PC += 4
        elif part[0] == 'sw':
            rt = part[1]
            imm, rs_reg = part[2].split('(')
            rs_reg = rs_reg[:-1]
            mem_address = reg[rs_reg] + int(imm)
            memory[mem_address] = reg[rt]
            counts['Memory'] += 1
            PC += 4
        elif part[0] == 'add':
            reg[part[1]] = reg[part[2]] + reg[part[3]]
            counts['ALU'] += 1
            PC += 4
        elif part[0] == 'sub':
            reg[part[1]] = reg[part[2]] - reg[part[3]]
            counts['ALU'] += 1
            PC += 4
        elif part[0] == 'slt':
            reg[part[1]] = 1 if reg[part[2]] < reg[part[3]] else 0
            counts['ALU'] += 1
            PC += 4
        elif part[0] == 'and':
            reg[part[1]] = reg[part[2]] & reg[part[3]]
            counts['ALU'] += 1
            PC += 4
        elif part[0] == 'sll':
            reg[part[1]] = reg[part[2]] << int(part[3])
            counts['ALU'] += 1
            PC += 4
        elif part[0] == 'srl':
            reg[part[1]] = reg[part[2]] >> int(part[3])
            counts['ALU'] += 1
            PC += 4
        elif part[0] == 'calc':
            reg[part[1]] = (reg[part[2]] ** 2 + 7) // 3
            counts['Special'] += 1
            PC += 4

        counts['Total'] += 1

        if single_step:
            print_registers(reg)
            print_memory(memory)
            print("PC after execution:", PC)
            input("Press Enter to continue...")

    if not single_step:
        print_registers(reg)
        print_memory(memory)
    print("Instruction counts:", counts)

def main():
    file_path = "program.asm"  # Using "program.asm" as the file path
    instructions = read_asm_file(file_path)

    parsed_instructions, labels = parse_labels_and_instructions(instructions)
    
    memory = {}
    reg = {f"${i}": 0 for i in range(32)}

    bin_instructions = [convert_to_binary(inst, labels, pc * 4) for pc, inst in enumerate(parsed_instructions)]

    print("Assembly to Machine Code Conversion:")
    for i, binary in enumerate(bin_instructions):
        if binary:  # Check if binary is not None
            print(f"{parsed_instructions[i]} -> {binary}")
        else:
            print(f"{parsed_instructions[i]} -> Invalid instruction")

    inD = {pc * 4: instr for pc, instr in enumerate(parsed_instructions)}
    
    sim(inD, labels, reg, memory, bin_instructions)

if __name__ == "__main__":
    main()
