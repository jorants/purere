import sre_compile
import sre_parse

from .constants import *


def replace_repeats(command_list):
    # This function rewrites all repeats in terms of:
    # - Simple repititions for minimal values
    # - branches for optional but limited repeats
    # - infinite optional repeats for the rest
    # This makes repeats stateless at the cost of a longer code.
    state = command_list.state
    new_pattern = sre_parse.SubPattern(state)

    for opcode, args in command_list:
        # # handle recursive opcodes:
        repeating_arg = {
            MAX_REPEAT: {2},
            MIN_REPEAT: {2},
            SUBPATTERN: {3},
            ASSERT: {1},
            ASSERT_NOT: {1},
            CALL: {},
            GROUPREF_EXISTS: {1, 2},
        }
        if opcode in repeating_arg:
            argpositions = repeating_arg[opcode]
            if not argpositions:
                # argument itself is repeating_arg
                args = replace_repeats(args)
            else:
                args = tuple(
                    replace_repeats(arg)
                    if i in argpositions and isinstance(arg, sre_parse.SubPattern)
                    else arg
                    for i, arg in enumerate(args)
                )

        elif opcode is BRANCH:
            # handle branch seperate aas it may have many children:
            args = (args[0], [replace_repeats(part) for part in args[1]])

        if opcode in {MAX_REPEAT, MIN_REPEAT}:
            mintimes, maxtimes, torepeat = args
            if len(torepeat) == 1 and opcode is MAX_REPEAT:
                repcode = torepeat[0][0]
                if ("ANY" in str(repcode).split("_")
                    or "IN" in str(repcode).split("_")
                    or "RANGE" in str(repcode).split("_")
                    or "LITERAL" in str(repcode).split("_")):
                    # keep repeats if there is only one
                    new_pattern.append((opcode,args))
                    continue
            
            if mintimes > 0:
                # unroll the minimal required parts
                new_pattern.data += torepeat.data * mintimes
                if maxtimes != MAXREPEAT:
                    maxtimes -= mintimes
                mintimes = 0
            empty = sre_parse.SubPattern(torepeat.state)
            if maxtimes != MAXREPEAT and maxtimes != 0:
                # we could now unroll a{0,5} as a?a?a?a?a?, but that would be a bad plan
                # this would casue a lot of backtracking, with all 2**5 combinations tried. Instead we use a series of branch operations: |a(|a(|a(|a(|a))))
                # altough funcitonally the same as |a|aa|aaa|aaaa|aaaaa, it ensures we do not keep checking the same constantly.
                # the order of branches matters for MIN/MAX

                newcode = []

                for number in range(maxtimes):
                    subpat = sre_parse.SubPattern(torepeat.state)
                    subpat.data = torepeat.data + newcode
                    if opcode is MAX_REPEAT:
                        newcode = [(BRANCH, (None, [subpat, empty]))]
                    else:
                        newcode = [(BRANCH, (None, [empty, subpat]))]

                new_pattern.data += newcode

            elif maxtimes is MAXREPEAT:
                # We need to optionally repeat forever, we rewrite this as a branch between a single go with a back jump or an empty string.
                # the jump back will be dealt with after compilation, for now we just rewrite a* as (a|)*
                empty = sre_parse.SubPattern(torepeat.state)
                newcode = sre_parse.SubPattern(torepeat.state)
                if opcode is MAX_REPEAT:
                    newcode.append((BRANCH, (None, [torepeat, empty])))
                else:
                    newcode.append((BRANCH, (None, [empty, torepeat])))
                new_pattern.append((opcode, (mintimes, maxtimes, newcode)))
        else:
            # non repeat opcode
            new_pattern.append((opcode, args))
    return new_pattern


def remove_repeats(code):
    # Takes code compiled after replace_repeats has ben called on it
    # changes repeats { (a|)* }into branches with anegative jump and without repeat
    for i, opcode in enumerate(code):
        if opcode is REPEAT:
            skip = code[i + 1]
            repeat_type = code[i + skip + 1]
            assert code[i + 4] is BRANCH
            branch_skip = code[i + 5]  # skip of the first branch
            if repeat_type is MAX_UNTIL:
                # First of the two branches should be nonempty and end in a jump
                assert code[i + branch_skip + 3] is JUMP
                # modify argument to JUMP to point to the start of the repeat
                code[i + branch_skip + 4] = -(branch_skip + 4)
            else:
                # end of the repeat should be after end of second branch
                assert code[i + skip - 2] is JUMP
                code[i + skip - 1] = -(skip - 1)
            code[i : i + 4] = [NOP] * 4
            code[i + skip + 1] = NOP
    return code


def info_len(code):
    if code[0] is INFO:
        return code[1] + 1
    else:
        return 0


def combine_literals(code):
    # Should be called on the parts
    i = 0
    while i < len(code):
        opcode = code[i]
        i += 1

        if opcode is IN or opcode is IN_UNI_IGNORE or opcode is IN_IGNORE:
            skip = code[i]
            i += skip
        elif opcode is LITERAL:
            j = i - 1
            while j < len(code) and code[j] is LITERAL:
                j += 2
            arguments = [code[pos] for pos in range(i, j, 2)]
            if len(arguments) > 1:
                code[i - 1] = LITERALS
                code[i] = arguments
                for k in range(i + 1, j):
                    code[k] = NOP
            i = j
    return code


def compile_without_repeat(regex, flags=0):
    parsed = sre_parse.parse(regex, flags)
    parsed = replace_repeats(parsed)
    code = sre_compile._code(parsed, flags)
    code = remove_repeats(code)
    return parsed.state, code
