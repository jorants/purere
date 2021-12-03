from .proccess import *
from .constants import *
from .constants import _NamedIntConstant
from . import topy

from .stdlib import sre_parse
from .stdlib import sre_compile



def code_to_parts(code,jump_locations):
    # Places we need to cut as we need to jump there
    intervals = [
        (a, b)
        for a, b in zip([0] + jump_locations, jump_locations + [len(code)])
        if a != b
    ]
    # we will eventually number by the parts, not code location, so keep te mapping between those two representations
    jump2parts = {loc: i for i, loc in enumerate(a for a, b in intervals)}
    parts2jump = {
        i: [loc] for i, loc in enumerate(a for a, b in intervals)
    }  # this last one will eventually contain multiple jump per part as we remove unneeded parts
    
    parts = [code[a:b] for a, b in intervals]
        
    # now that we have the code blocks and a mapping of jumps we can remove all nops,but first combine literals as this creates more NOPS:
    for p in parts:
        apply_func_code(p,combine_literals)
        #parts = [combine_literals(part) for part in parts]
    parts = [[c for c in code if not c is NOP] for code in parts]

    # some parts are simply a jump to another part, we should take those out and point to target directly
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


    # Now we have the new mappings set we are done with parts2jumps so we do not need to update it
    # give the parts a brand new name and create a mpapping of old part numbers to new ones
    # Make sure they stay in the same order
    new_names = {oldname: i for i, oldname in enumerate(sorted(list(set(jump2parts.values()))))}

    # filter the parts for the ones we keep
    parts = [part for i, part in enumerate(parts) if i in new_names]
    # Change to the new names  for the jump lookup
    jump2parts = {j: new_names[p] for j, p in jump2parts.items()}


    # with the cleaning out of the way we can remap jumps and branches so the point at parts instead of codelins
    for p in parts:
        apply_func_code(p,remap_jumps,mapping=jump2parts)
    return parts

def info_len(code):
    if code[0] is INFO:
        return code[1] + 1
    else:
        return 0
                
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

    # Use stdlib's sre_parse to create an AST
    parsed = sre_parse.parse(regex, flags)
    # We reshuffel loops to be easier to parse
    parsed = apply_func_ast(parsed,split_repeats)
    parsed = apply_func_ast(parsed,unroll_small) 
    parsed = apply_func_ast(parsed,padd_loops)

    # this marks the groups that might match an empty string by negating their group number
    # This is done so we can later add them to referenced_groups, and ensure that their bounderaies are kept track of.
    # This way they are checked wether the can match an empty string
    parsed = apply_func_ast(parsed,empty_groups)

    
    # use stdlib's sre_compile to compile to VM code
    code = sre_compile._code(parsed, flags)


    # Handle the info block seperatly
    infolen = info_len(code)   
    info, code = code[:infolen], code[infolen:]
    
    # finishe the reshuffeling of loop
    apply_func_code(code,rename_repeats)
    apply_func_code(code,rewrite_unbounded_repeats)
    # we pass a list so the functions can change its value globally
    loop_counter = [0]
    apply_func_code(code,rewrite_fixed_repeats,loop_counter=loop_counter)
    apply_func_code(code,rewrite_bounded_repeats,loop_counter=loop_counter)

    apply_func_code(code,add_assert_ends)

    apply_func_code(code,optimize_any)
    
    # Transform all jumps into into absolute jumps
    # Also save these absolute jumps for later    
    jump_locations = sorted(list(set(
        apply_func_code(code,absolute_jump_locations))))

    # This gets the previously marked groups and undoes the marking 
    empty_marks = apply_func_code(code,fix_negative_marks)
    
    # parse the info
    info = parse_info(info, flags=flags)
    state = parsed.state
    info["groups"] = state.groups
    info["groupdict"] = state.groupdict
    info["flags"] |= state.flags

    # get the maximum mark number in the code, impotant for the python code generation
    allmarks = get_all_args({MARK}, code)
    maxmark = max(allmarks) if allmarks else -1
    
    # Get all groups that are refrenced, their marks are important for the state of the backtracker and should be saved seperatly
    # Possible TODO: handle empty groups seperate as we only need to keep track of their empty/non-empty state, not the whole marks
    refrenced_groups = get_all_args({GROUPREF, ABS_GROUPREF_EXISTS}, code)
    tracked_groups = sorted(list(refrenced_groups | set(empty_marks)))
    # Mapping from actual MARK argument to the position in the state
    statemarks = {2 * i: 2 * j for j, i in enumerate(tracked_groups)}
    statemarks.update({2 * i + 1: 2 * j + 1 for j, i in enumerate(tracked_groups)})

    # splits the code into seperate parts
    parts = code_to_parts(code,jump_locations)

    # pass of the work to topy.py to compile this into python code
    pycode = topy.parts_to_py(
        parts,
        name=name,
        comment=f"Regex: {repr(regex)}",
        flags=flags,
        marknum=maxmark + 1,
        statemarks=statemarks,
        loopnum = loop_counter[0]
    )
    
    if flags & SRE_FLAG_DEBUG:
        print("---------------------- Main code ------------------------")
        for i, l in enumerate(pycode.split("\n")):
            #print(l)
            print(i + 1, l)
    #compile the python code
    res = {}
    exec(pycode, res)
    return info, res[name]
