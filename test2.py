def hexBin(hex_value):
    return format(int(hex_value, 16), '032b')

def print_registers(reg):
    print("Registers:")
    for i in range(0, 32, 4):  # Print 4 registers per line
        print(
            f"${i:2}: {reg[f'${i}']:10} | ${i+1:2}: {reg[f'${i+1}']:10} | ${i+2:2}: {reg[f'${i+2}']:10} | ${i+3:2}: {reg[f'${i+3}']:10}"
        )
    print()

def print_memory(memory):
    print("Memory:")
    non_zero_addresses = [
        address for address, value in memory.items() if value != 0
    ]
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

    if opcode == '000000':  # R-types
        rs = mc[6:11]
        rt = mc[11:16]
        rd = mc[16:21]
        shamt = mc[21:26]
        funct = mc[26:]

        if funct in functs:
            if funct == '000000' or funct == '000010':
                asm.append(
                    f"{functs[funct]} ${int(rd, 2)}, ${int(rt, 2)}, {int(shamt, 2)}"
                )
            elif funct == '111111':
                asm.append(f"{functs[funct]} ${int(rd, 2)}, ${int(rs, 2)}")
            else:
                asm.append(f"{functs[funct]} ${int(rd, 2)}, ${int(rs, 2)}, ${int(rt, 2)}")

    elif opcode in op:  # I-types
        rs = mc[6:11]
        rt = mc[11:16]
        imm0 = mc[16:]
        imm = int(imm0, 2)

        if imm0[0] == '1':  # Sign extension for negative numbers
            imm -= 1 << len(imm0)

        if opcode == '100011' or opcode == '101011':
            asm.append(f"{op[opcode]} ${int(rt, 2)}, {imm}(${int(rs, 2)})")
        elif opcode == '000010':
            asm.append(f"{op[opcode]} {imm}")
        else:
            asm.append(f"{op[opcode]} ${int(rt, 2)}, ${int(rs, 2)}, {imm}")

def sim(inD, reg, memory, binList):
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

    mode = input(
        "Enter 'n' for single instruction mode, 'a' for automatic mode: "
    )
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
            rs = int(reg[part[2]])
            imm = int(part[3])
            reg[part[1]] = rs + imm
            counts['ALU'] += 1
            PC += 4

        elif part[0] == 'beq':
            rs = reg[part[2]]
            rt = reg[part[1]]
            imm = int(part[3])
            if rs == rt:
                PC += (imm * 4) + 4
            else:
                PC += 4
            counts['Branch'] += 1

        elif part[0] == 'bne':
            rs = reg[part[2]]
            rt = reg[part[1]]
            imm = int(part[3])
            if rs != rt:
                PC += (imm * 4) + 4
            else:
                PC += 4
            counts['Branch'] += 1

        elif part[0] == 'j':
            imm = int(part[1])
            PC = (PC & 0xF0000000) | (imm << 2)
            counts['Jump'] += 1

        elif part[0] == 'lw':
            rt = part[1]
            imm, rs_reg = part[2].split('(')
            rs_reg = rs_reg[:-1]  # remove the closing parenthesis
            rs = int(reg[rs_reg])
            mem_address = rs + int(imm)
            reg[rt] = memory.get(mem_address, 0)
            counts['Memory'] += 1
            PC += 4

        elif part[0] == 'sw':
            rt = part[1]
            imm, rs_reg = part[2].split('(')
            rs_reg = rs_reg[:-1]  # remove the closing parenthesis
            rs = int(reg[rs_reg])
            rt_val = int(reg[rt])
            mem_address = rs + int(imm)
            memory[mem_address] = rt_val
            counts['Memory'] += 1
            PC += 4

        elif part[0] == 'and':
            rs = int(reg[part[2]])
            rt = int(reg[part[3]])
            result = rs & rt
            reg[part[1]] = result
            counts['ALU'] += 1
            PC += 4

        elif part[0] == 'sll':
            rd = part[1]
            rt = int(reg[part[2]])
            shamt = int(part[3])
            reg[rd] = rt << shamt
            counts['ALU'] += 1
            PC += 4

        elif part[0] == 'srl':
            rd = part[1]
            rt = int(reg[part[2]]) & 0xFFFFFFFF
            shamt = int(part[3])
            reg[rd] = rt >> shamt
            counts['ALU'] += 1
            PC += 4

        elif part[0] == 'sub':
            rs = int(reg[part[2]])
            rt = int(reg[part[3]])
            reg[part[1]] = rs - rt
            counts['ALU'] += 1
            PC += 4

        elif part[0] == 'slt':
            rs = int(reg[part[2]])
            rt = int(reg[part[3]])
            reg[part[1]] = 1 if rs < rt else 0
            counts['Other'] += 1
            PC += 4

        elif part[0] == 'add':
            rs = int(reg[part[2]])
            rt = int(reg[part[3]])
            reg[part[1]] = rs + rt
            counts['ALU'] += 1
            PC += 4

        elif part[0] == 'calc':
            rd = part[1]
            rs = reg[part[2]]
            hex_str = hex(rs & 0xFFFFFFFF)[2:].lower()
            C = hex_str.count('e') + hex_str.count('f')
            reg[rd] = C
            counts['Special'] += 1
            PC += 4

        if single_step:
            print("PC after execution:", PC)
            print_registers(reg)
            print_memory(memory)

    counts['Total'] = sum(v for v in counts.values())
    print("\nExecution Completed.")
    print(f"Instructions Executed: {counts['Total']}")
    print(f"ALU Instructions: {counts['ALU']}")
    print(f"Jump Instructions: {counts['Jump']}")
    print(f"Branch Instructions: {counts['Branch']}")
    print(f"Memory Instructions: {counts['Memory']}")
    print(f"Special Instructions: {counts['Special']}")
    print(f"Other Instructions: {counts['Other']}")
    print_registers(reg)
    print_memory(memory)