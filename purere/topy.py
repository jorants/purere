from .constants import *
from .constants import _NamedIntConstant

def get_ctopy(flags=0):
    # ctopy converts a integer to the correspoinding python (bytes or str) representation
    if flags & SRE_FLAG_BYTE_PATTERN:
        return lambda x: repr(x.to_bytes(1, "big"))
    else:
        return lambda x: repr(chr(x))


def offset_str(offset):
    if offset == 0:
        return ""
    elif offset < 0:
        return str(offset)
    elif offset > 0:
        return "+" + str(offset)


def get_val(offset=0, flags=0):
    if flags & SRE_FLAG_BYTE_PATTERN:
        val = f"s[pos{offset_str(offset)}:pos{offset_str(offset+1)}]"  # to get a bytes object back
    else:
        val = f"s[pos{offset_str(offset)}]"
    return val


def get_category_condition(cat, val, flags=0):
    ctopy = get_ctopy(flags)
    parts = str(cat).split("_")
    isunicode = "UNI" in parts
    negated = "NOT" in parts

    if "WORD" in parts:
        base = f"({val}.isalnum() or {val} == {ctopy(95)})"  # 95 = '_'
    elif "SPACE" in parts and "UNI" not in parts:
        base = f"({val}.isspace() and not {ctopy(0x1c)} <= {val} <= {ctopy(0x1f)})"
    elif "SPACE" in parts:
        base = f"{val}.isspace()"
    elif "DIGIT" in parts:
        # for some reason the real unicode definition does not agree with ASCII on ASCII chars... see issue
        if "UNI" in parts and (flags & SRE_FLAG_STRICT_UNICODE):
            base = f"unicodedata.category({val})=='Nd'"
        elif "UNI" in parts:
            # not the real definition for unicode but close enough if unicode data is not avalible
            base = f"{val}.isnumeric()"
        else:
            base = f"{ctopy(48)} <= {val} <= {ctopy(57)}"
    elif "LINEBREAK" in parts:
        # Not sure what this class is, but we can reverse engeneer it from sre
        # This one also does not agree between unicode ans ascii
        if "UNI" in parts:
            base = (
                f"({ctopy(0x0a)} <= {val} <= {ctopy(0x0d)} or {ctopy(0x1c)} <= {val} <= {ctopy(0x1e)} or {val} in"
                "{'\\x85','\\u2028','\\u2029'})"
            )  # we do not use c to py the as this will always be a string
        else:
            base = f"{val} == {ctopy(0x0a)}"
    else:
        raise NotImplementedError(f"Category not implemented: {cat}")

    if not isunicode:
        base = f"(num({val})<128 and {base})"
    if negated:
        return f"not {base}"
    else:
        return base


def literals_to_cond(code, i, flags=0):
    # ctopy converts a integer to the correspoinding python (bytes or str) representation
    ctopy = get_ctopy(flags)
    pre = []
    conditions = []
    neged = False
    val = get_val(flags=flags)

    parts = str(code[i]).split("_")
    if code[i] is IN or code[i] is IN_UNI_IGNORE or code[i] is IN_IGNORE:
        # whole class of things
        inlen = code[i + 1]
        end = i + 1 + inlen
        i += 2
        single = False
    else:
        # only grab first condition
        single = True

    baseval = val
    if "UNI" in parts and "IGNORE" in parts:
        pre.append(f"val = {val}.lower()")
        val = "val"
    elif "IGNORE" in parts:
        pre.append(f"val = ({val}.lower() if num({val})<128 else {val})")
        val = "val"

    while single or i <= end:
        opcode = code[i]
        i += 1
        if opcode is FAILURE:
            break

        if "LITERAL" in str(opcode):
            parts = str(opcode).split("_")
            noted = "not" if "NOT" in parts else ""
            arg = code[i]
            char = ctopy(arg)
            i += 1
            conditions.append(f"{noted}({char} == {val})")
        elif "RANGE" in str(opcode):
            minval, maxval = code[i], code[i + 1]
            minchar, maxchar = ctopy(minval), ctopy(maxval)
            i += 2
            # Some unicode ranges are not translated by sre_parse for some reason, so in unicode ignore mode we check both upper, lower and the roiginal
            conditions.append(f"{minchar} <= {val} <= {maxchar}")
            if opcode is RANGE_UNI_IGNORE:
                conditions.append(f"{minchar} <= {baseval} <= {maxchar}")
                conditions.append(f"{minchar} <= {baseval}.upper() <= {maxchar}")
        elif opcode is CATEGORY:
            cat = code[i]
            conditions.append(get_category_condition(cat, val, flags=flags))
            i += 1
        elif opcode is NEGATE:
            neged = True
        elif opcode is CHARSET:
            bits = code[i : i + 8]
            pre.append(f"bitmapnum = num({val}) // 32")
            pre.append(f"bitnum = num({val}) - bitmapnum*32")
            conditions.append(f"(num({val}) < 256 and ({bits}[bitmapnum] & (1 << bitnum)))")
            i += 8
        elif opcode is ANY_ALL:
            conditions.append("True")
        elif opcode is ANY:
            conditions.append(f"{val} != {ctopy(10)}")
        elif opcode is BIGCHARSET:
            numchunks = code[i]
            oldi = i
            i += 1
            blocknums = b"".join(c.to_bytes(4, "little") for c in code[i : i + 64])
            i += 64
            blocks = [code[i + j * 8 : i + (j + 1) * 8] for j in range(numchunks)]
            i += numchunks * 8
            pre.append(f"blocknums{oldi} = {repr(blocknums)}")
            pre.append(f"blocks{oldi} = {repr(blocks)}")
            pre.append(f"blocknum{oldi} = blocknums{oldi}[num({val})//256]")
            pre.append(f"block{oldi} = blocks{oldi}[blocknum{oldi}]")
            pre.append(f"blockindex{oldi} = num({val}) % 256")
            pre.append(f"relword{oldi} = block{oldi}[blockindex{oldi} // 32]")
            pre.append(
                f"res{oldi} = bool(relword{oldi} & (1<<(blockindex{oldi} % 32)))"
            )
            conditions.append(f"res{oldi}")
        else:
            raise NotImplementedError(f"Unknown character matching opcode: {opcode}")

        if single:
            return pre, conditions, neged, i
    return pre, conditions, neged, i


def part_to_py(part, partnum, flags=0, statemarks={}):
    lines = [f"done.add((part,pos,smarks,loops))"]
    emit = lines.append
    oldi = 0
    i = 0

    def emit_fail(indent=0):
        emit(indent * " " + "break")

    def emit_comment():
        emit(f"# ^  {str(part[oldi:i])}")

    while i < len(part):
        oldi = i
        opcode = part[i]
        i += 1
        if opcode is ABS_JUMP:
            to = part[i]
            emit(f"part = {to}")
            if to < partnum:
                # skip to start only if we need to go back in partnum
                emit(f"continue")
            i += 1
            emit_comment()
            break
        elif opcode is LS_BRANCH:
            to = part[i]
            if len(to) > 1:
                revlist = to[::-1]
                emit(f"for target in {revlist}:")
                emit("  stack.append((target,pos,marks,smarks,loops))")
            else:
                emit(f"stack.append(({to[0]},pos,marks,smarks,loops))")
            i += 1
        elif (
            "ANY" in str(opcode).split("_")
            or "IN" in str(opcode).split("_")
            or "RANGE" in str(opcode).split("_")
            or "LITERAL" in str(opcode).split("_")
        ):
            pre, conds, neged, i = literals_to_cond(part, i - 1, flags=flags)
            opparts = str(opcode).split("_")

            emit("if pos >= endpos: break")
            for p in pre:
                emit(p)

            emit(f"if {'not' if not neged else ''} ({' or '.join(conds)}):")
            emit_fail(indent=1)
            emit("pos += 1")
        elif opcode is AT:

            # from _PyUnicode_IsLinebreak in cpython.
            newlines = {
                0x000A,
                0x000B,
                0x000C,
                0x000D,
                0x001C,
                0x001D,
                0x001E,
                0x0085,
                0x2028,
                0x2029,
            }
            if flags & SRE_FLAG_BYTE_PATTERN:
                newlines = {nl for nl in newlines if nl < 128}

            val = get_val(flags=flags)
            preval = get_val(offset=-1, flags=flags)
            if flags & SRE_FLAG_BYTE_PATTERN:
                val = "s[pos:pos+1]"  # to get a bytes object back
                preval = "s[pos-1:pos]"
            else:
                val = "s[pos]"
                preval = "s[pos-1]"

            arg = part[i]
            i += 1
            if (
                arg is AT_BEGINNING_STRING or arg is AT_BEGINNING
            ):  # ^ and \A really want the actual start
                emit(f"if not pos == 0:")
            elif arg is AT_BEGINNING_LINE:
                emit(f"if not(pos == 0 or num({preval}) in {newlines}):")
            elif (
                arg is AT_END
            ):  # for some reason $ does not want the actual end but endpos
                emit(
                    f"if not (pos == endpos or (pos == endpos-1 and num({val}) in {newlines})):"
                )
            elif arg is AT_END_STRING:
                emit("if not pos == endpos:")
            elif arg is AT_END_LINE:
                emit(f"if not(pos == len(s) or num({val}) in {newlines}):")
            elif arg in {
                AT_BOUNDARY,
                AT_NON_BOUNDARY,
                AT_UNI_BOUNDARY,
                AT_UNI_NON_BOUNDARY,
            }:
                if "UNI" in str(arg):
                    now_word = get_category_condition("UNI_WORD", val, flags)
                    was_word = get_category_condition("UNI_WORD", preval, flags)
                else:
                    now_word = get_category_condition("WORD", val, flags)
                    was_word = get_category_condition("WORD", preval, flags)
                emit("if len(s) == 0: break")
                emit(f"at_b = (pos == 0 and {now_word})")
                emit(f"at_b = at_b or (pos == len(s) and {was_word})")
                emit(
                    f"at_b = at_b or (not(pos==0 or pos==len(s)) and not({now_word}) and {was_word})"
                )
                emit(
                    f"at_b = at_b or (not(pos==0 or pos==len(s)) and {now_word} and not({was_word}))"
                )

                if "NON" in str(arg):
                    emit("if at_b:")
                else:
                    emit("if not at_b:")
            else:
                raise NotImplementedError(f"Unknown AT argument: {arg}")
            emit_fail(indent=1)
        elif opcode is LITERALS:
            arg = part[i]
            i += 1
            arglen = len(arg)
            if flags & SRE_FLAG_BYTE_PATTERN:
                teststr = repr(b"".join(x.to_bytes(1, "big") for x in arg))
            else:
                teststr = repr("".join(chr(x) for x in arg))

            emit(
                f"if not(pos+{arglen} <= endpos) or s[pos:pos+{arglen}] != {teststr}: break"
                # Whould be ever so slightly faster but does not work with exotic byteliker types....
                #f"if not(s.startswith({teststr},pos)): break"
            )
            emit(f"pos += {arglen}")
        elif opcode is SUCCESS:
            emit(
                "if ((full and pos == endpos) or not full) and (not nonempty or pos!=startpos):"
            )
            emit(" return True,pos,marks,done")
            emit("else:")
            emit(" break")
            emit_comment()
            break
        elif opcode is MARK:
            tomark = part[i]
            emit(f"marks = marks[:{tomark}]+ (pos,) +marks[{tomark+1}:]")
            if tomark in statemarks:
                stomark = statemarks[tomark]
                emit(f"smarks = smarks[:{stomark}]+ (pos,) +smarks[{stomark+1}:]")
            i += 1
        elif opcode is GROUPREF:
            group = part[i]
            i += 1
            emit(f"submatch = s[marks[{group*2}]:marks[{group*2+1}]]")
            emit("if not s[pos:pos+len(submatch)] == submatch:")
            emit_fail(indent=1)
            emit("pos+=len(submatch)")
        elif opcode is GROUPREF_UNI_IGNORE:
            group = part[i]
            i += 1
            emit(f"submatch = s[marks[{group*2}]:marks[{group*2+1}]].lower()")
            emit("if not s[pos:pos+len(submatch)].lower() == submatch:")
            emit_fail(indent=1)
            emit("pos+=len(submatch)")
        elif opcode is GROUPREF_IGNORE:
            group = part[i]
            i += 1
            emit(f"submatch = s[marks[{group*2}]:marks[{group*2+1}]]")
            emit("nextpart = s[pos:pos+len(submatch)]")
            emit(
                "if not all((a == b or (a<128 and b<128 and a.lower() == b.lower())) for a,b in zip(nextpart,submatch)):"
            )
            emit_fail(indent=1)
            emit("pos+=len(submatch)")
        elif opcode is ABS_GROUPREF_EXISTS:
            group, jumploc = part[i : i + 2]
            i += 2
            emit(f"if marks[{group*2+1}] == None:")
            emit(f" part = {jumploc}")
            emit(" continue")
        elif opcode is ABS_REPEAT_ONE:
            # handle REPEAT_ONE directly as we can easily loop localy
            nextpart, minrep,maxrep = part[i:i+3]
                        
            looplines = part_to_py(part[i+3:-1],0,flags=flags)
            looplines = [line for line in looplines if "part +=" not in line]
            looplines = [line for line in looplines if "done.add" not in line]
            
            if minrep>0:
                emit("correct = False")
                emit(f"for rep in range({minrep}):")
                lines += indent(looplines,indent=1)
                emit("else:")
                emit(" correct = True")
                emit("if not correct:")
                emit_fail(indent=1)       
            if maxrep!=minrep:
                emit("correct = False")
                if maxrep is MAXREPEAT:
                    emit("while True:")
                else:
                    emit(f"for rep in range({maxrep-minrep}):")
                # Now we may jump out of the loop if we can not get another itteration
                emit(f" stack.append(({nextpart},pos,marks,smarks,loops))")
                lines += indent(looplines,indent=1)
                emit("else:")
                emit(" correct = True")
                emit("if not correct:")
                emit_fail(indent=1)       
            i = len(part)
        elif opcode is SET_COUNTER:
            counter,value = part[i:i+2]
            i+=2
            emit(f"loops = loops[:{counter}]+ ({value},) +loops[{counter+1}:]")
        elif opcode is ABS_JUMP_IF_COUNTER:
            counter,target = part[i:i+2]
            i+=2
            # This is always after a loop, decrease the counter first as we already did one loop
            emit(f"loops = loops[:{counter}]+ (loops[{counter}]-1,) +loops[{counter+1}:]")
            emit(f"if loops[{counter}] > 0:")
            emit(f" part = {target}")
            emit(f" continue")
        else:
            if not isinstance(opcode,_NamedIntConstant):
                raise ValueError(f"Wrong code {opcode}")
            raise NotImplementedError(f"Unknown opcode: {opcode}")
        emit_comment()

    else:
        # last command changed part so we do not have to
        emit("part += 1")
    return lines


def indent(lines, indent=4):
    return [" " * indent + l for l in lines]


def parts_to_py(
        parts, name="regexfunction", comment="", flags=0, marknum=0, statemarks={}, loopnum = 0
):
    if flags & SRE_FLAG_LOCALE:
        raise NotImplementedError("Locale matching (L flag) is not supported")

    codelines = [
        f"def {name}(s, pos = 0, endpos = None, full = False, nonempty = False, done = None):",
        f" # {comment}",
        " num = lambda x: x[0]" if flags & SRE_FLAG_BYTE_PATTERN else " num = ord",
        " startpos = pos",
        " endpos = len(s) if endpos is None else min(endpos,len(s))",
        " if done == None:",
        "  done = set()",
        #" done = set()",
        f" marks = (None,)*{marknum}",
        f" smarks = (None,)*{len(statemarks)}",
        f" loops = (None,)*{loopnum}",
        " stack = [(0,pos,marks,smarks,loops)]",
        " while stack:",
        "  part,pos,marks,smarks,loops = stack.pop()",
        "  while (part,pos,smarks,loops) in done and stack:",
        "   part,pos,marks,smarks,loops = stack.pop()",
        "  if (part,pos,smarks,loops) in done:",
        "   break",
        "",
        "  while True:",
    ]

    for i, part in enumerate(parts):
        codelines.append(f"   ")
        codelines.append(f"   if part == {i}:")
        codelines += indent(part_to_py(part, i, flags=flags, statemarks=statemarks))
    codelines.append(" return None, None, None, done")
    code = "\n".join(codelines)

    if "unicodedata" in code:
        # only import this if it is used
        codelines.insert(2, " import unicodedata")
        code = "\n".join(codelines)
    return code
