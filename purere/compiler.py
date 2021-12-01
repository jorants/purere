from .proccess import compile_without_repeat, info_len, combine_literals, apply_func_code
from .constants import *
from .constants import _NamedIntConstant
from .dis import dis
from . import topy


def iter_jump_locations(code):
    for i, opcode in enumerate(code):
        if opcode is ABS_JUMP:
            yield code[i + 1]
        elif opcode is LS_BRANCH:
            yield from code[i + 1]
        elif opcode is ABS_GROUPREF_EXISTS:
            yield code[i + 2]
        elif opcode is ABS_REPEAT_ONE:
            yield code[i+1]


            

def absolute_jump_locations(code):
    # changes code to have absolute jumps and branch to have a list of arguments
    # Two new opcodes are introduced for this ABS_JUMP and LS_BRANCH
    itt = enumerate(code)
    for i, opcode in itt:
        if opcode is JUMP:
            _, reljump = next(itt)
            code[i] = ABS_JUMP
            code[i + 1] = i + 1 + reljump
        elif opcode is BRANCH:
            loc = i + 1 + code[i + 1]
            locations = [loc]
            while not code[loc] is FAILURE:
                loc = loc + code[loc]
                locations.append(loc)
            code[i] = LS_BRANCH
            code[i + 1] = locations[:-1]  # leave out the final FAILURE
            for l in locations:
                code[l] = NOP
        elif opcode is GROUPREF_EXISTS:
            _, groupnum = next(itt)
            j, reljump = next(itt)
            code[i] = ABS_GROUPREF_EXISTS
            code[j] = j + reljump - 1
        elif opcode is REPEAT_ONE:
            _, reljump = next(itt)
            code[i] = ABS_REPEAT_ONE
            code[i+1] = i + reljump + 1
    return code


def remap_jumps(code, mapping):
    for i, opcode in enumerate(code):
        if opcode is ABS_JUMP:
            code[i + 1] = mapping[code[i + 1]]
        elif opcode is LS_BRANCH:
            code[i + 1] = [mapping[v] for v in code[i + 1]]
        elif opcode is ABS_GROUPREF_EXISTS:
            code[i + 2] = mapping[code[i + 2]]
        elif opcode is ABS_REPEAT_ONE:
            code[i + 1] = mapping[code[i + 1]]
    return code


def code_to_parts(code):
    # Trnasform into absolute jumps before we start cutting things up
    code = absolute_jump_locations(code)
    # Places we need to cut as we need to jump there
    jump_locations = sorted(list(set(iter_jump_locations(code))))
    intervals = [
        (a, b)
        for a, b in zip([0] + jump_locations, jump_locations + [len(code)])
        if a != b
    ]
    # we will eventually number by the parts, not code location, so keep te mapping between those two representations
    jump2parts = {loc: i for i, loc in enumerate(a for a, b in intervals)}
    parts2jump = {
        i: [loc] for i, loc in enumerate(a for a, b in intervals)
    }  # will eventually contain multiple jump
    parts = [code[a:b] for a, b in intervals]

    # now that we have the code blocks and a mapping of jumps we kan remove all nops,but first combine literals:
    for p in parts:
        apply_func_code(p,combine_literals)
        #parts = [combine_literals(part) for part in parts]
    parts = [[c for c in code if not c is NOP] for code in parts]

    # some parts are simply a jump to another part, we should take those out and point to target
    # Some might have become nothing more than NOP opperations, take those out as well and point to next one
    for partnum, part in enumerate(parts):
        if len(part) == 2 and part[0] is ABS_JUMP:
            newpartnum = jump2parts[part[1]]
        elif len(part) == 0 and partnum + 1 < len(parts):
            newpartnum = partnum + 1
        else:
            continue

        oldjumpnums = parts2jump[partnum]
        for jn in oldjumpnums:
            jump2parts[jn] = newpartnum
        parts2jump[newpartnum] += oldjumpnums

    # Now we ave the new mappings set we are done with parts2jumps so we do not need to update is
    # we do still need jumps2part
    new_names = {oldname: i for i, oldname in enumerate(set(jump2parts.values()))}
    parts = [part for i, part in enumerate(parts) if i in new_names]
    jump2parts = {j: new_names[p] for j, p in jump2parts.items()}

    # with the cleaning out of the way we can remap jumps and branches so the point at parts instead of codelins
    parts = [remap_jumps(code, jump2parts) for code in parts]
    return parts


def parse_info(code, flags=0):

    code = code[1:]
    skip, infoflags, min, max = code[:4]
    if max == MAXREPEAT:
        max = "MAXREPEAT"
    start = 4
    checker = None
    fixed_prefix = None
    if infoflags & SRE_INFO_PREFIX:
        prefix_len, prefix_skip = code[4:6]
        start = 6
        prefix = code[start : start + prefix_len]
        if flags & SRE_FLAG_BYTE_PATTERN:
            prefix = b"".join(map(lambda x: x.to_bytes(1, "big"), prefix))
        else:
            prefix = "".join(map(chr, prefix))
        start += prefix_len
        overlap = code[start : start + prefix_len]
        start += prefix_len
        #checker = lambda s, pos: s.startswith(prefix,pos)
        #checker = lambda s, pos: s[pos : pos + len(prefix)] == prefix
        fixed_prefix = prefix
        
    if infoflags & SRE_INFO_CHARSET:
        charset = code[start:skip]
        pre, conditions, neged, _ = topy.literals_to_cond(
            [IN, len(charset)] + charset, 0, flags=flags
        )
        if flags & SRE_FLAG_BYTE_PATTERN:
            pre = ["num = lambda x: x[0]"] + pre
        else:
            pre = ["num = ord"] + pre
        codelines = ["def checkprefix(s,pos):"]
        codelines += topy.indent(pre, 1)
        codelines.append(f" return {' or '.join(conditions)}")
        pycode = "\n".join(codelines)
        if flags & SRE_FLAG_DEBUG:
            print("---------------------- Prefix-Checker code ------------------------")
            for i, l in enumerate(pycode.split("\n")):
                print(i + 1, l)
        res = {}
        exec(pycode, res)
        checker = res["checkprefix"]

    return {
        "flags": flags,
        "min": min,
        "max": max,
        "prefix_checker": checker,
        "fixed_prefix": fixed_prefix,
    }


def get_all_args(opcodes, code):
    found = set()
    for i, c in enumerate(code):
        if isinstance(c, _NamedIntConstant) and any(c is code for code in opcodes):
            found.add(code[i + 1])
    return found


def compile_regex(regex, flags=0, name="regex"):
    #flags |= SRE_FLAG_DEBUG
    if isinstance(regex, bytes):
        flags |= SRE_FLAG_BYTE_PATTERN

    state, code = compile_without_repeat(regex, flags)
    infolen = info_len(code)
    info, code = code[:infolen], code[infolen:]

    info = parse_info(info, flags=flags)

    info["groups"] = state.groups
    info["groupdict"] = state.groupdict
    info["flags"] |= state.flags

    allmarks = get_all_args({MARK}, code)
    maxmark = max(allmarks) if allmarks else -1

    # Get all groups that are refrenced, their marks are important for the state of the backtracker
    refrenced_groups = get_all_args({GROUPREF, GROUPREF_EXISTS}, code)
    # Mapping from actual MARK argument to the position in the state
    statemarks = {2 * i: 2 * j for j, i in enumerate(refrenced_groups)} | {
        2 * i + 1: 2 * j + 1 for j, i in enumerate(refrenced_groups)
    }

    parts = code_to_parts(code)

    pycode = topy.parts_to_py(
        parts,
        name=name,
        comment=f"Regex: {repr(regex)}",
        flags=flags,
        marknum=maxmark + 1,
        statemarks=statemarks,
    )
    if flags & SRE_FLAG_DEBUG:
        print("---------------------- Main code ------------------------")
        for i, l in enumerate(pycode.split("\n")):
            print(i + 1, l)
    res = {}
    exec(pycode, res)
    return info, res[name]
