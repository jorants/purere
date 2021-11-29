from .constants import *
from sre_compile import _hex_code, _CODEBITS


def dis(code, printfunc=print):
    import sys

    labels = set()
    level = 0
    offset_width = len(str(len(code) - 1))

    def dis_(start, end):
        def print_(*args, to=None):
            if to is not None:
                labels.add(to)
                args += ("(to %d)" % (to,),)
            printfunc(
                "%*d%s " % (offset_width, start, ":" if start in labels else "."),
                end="  " * (level - 1),
            )
            printfunc(*args)

        def print_2(*args):
            printfunc(end=" " * (offset_width + 2 * level))
            printfunc(*args)

        nonlocal level
        level += 1
        i = start
        while i < end:
            start = i
            op = code[i]
            i += 1
            op = OPCODES[op]
            if op in (SUCCESS, FAILURE, ANY, ANY_ALL, MAX_UNTIL, MIN_UNTIL, NEGATE):
                print_(op)
            elif op in (
                LITERAL,
                NOT_LITERAL,
                LITERAL_IGNORE,
                NOT_LITERAL_IGNORE,
                LITERAL_UNI_IGNORE,
                NOT_LITERAL_UNI_IGNORE,
                LITERAL_LOC_IGNORE,
                NOT_LITERAL_LOC_IGNORE,
            ):
                arg = code[i]
                i += 1
                print_(op, "%#02x (%r)" % (arg, chr(arg)))
            elif op is AT:
                arg = code[i]
                i += 1
                arg = str(ATCODES[arg])
                assert arg[:3] == "AT_"
                print_(op, arg[3:])
            elif op is CATEGORY:
                arg = code[i]
                i += 1
                arg = str(CHCODES[arg])
                assert arg[:9] == "CATEGORY_"
                print_(op, arg[9:])
            elif op in (IN, IN_IGNORE, IN_UNI_IGNORE, IN_LOC_IGNORE):
                skip = code[i]
                print_(op, skip, to=i + skip)
                dis_(i + 1, i + skip)
                i += skip
            elif op in (RANGE, RANGE_UNI_IGNORE):
                lo, hi = code[i : i + 2]
                i += 2
                print_(op, "%#02x %#02x (%r-%r)" % (lo, hi, chr(lo), chr(hi)))
            elif op is CHARSET:
                print_(op, _hex_code(code[i : i + 256 // _CODEBITS]))
                i += 256 // _CODEBITS
            elif op is BIGCHARSET:
                import _sre

                arg = code[i]
                i += 1
                mapping = list(
                    b"".join(
                        x.to_bytes(_sre.CODESIZE, sys.byteorder)
                        for x in code[i : i + 256 // _sre.CODESIZE]
                    )
                )
                print_(op, arg, mapping)
                i += 256 // _sre.CODESIZE
                level += 1
                for j in range(arg):
                    print_2(_hex_code(code[i : i + 256 // _CODEBITS]))
                    i += 256 // _CODEBITS
                level -= 1
            elif op in (
                MARK,
                GROUPREF,
                GROUPREF_IGNORE,
                GROUPREF_UNI_IGNORE,
                GROUPREF_LOC_IGNORE,
            ):
                arg = code[i]
                i += 1
                print_(op, arg)
            elif op is JUMP:
                skip = code[i]
                print_(op, skip, to=i + skip)
                i += 1
            elif op is BRANCH:
                skip = code[i]
                print_(op, skip, to=i + skip)
                while skip:
                    dis_(i + 1, i + skip)
                    i += skip
                    start = i
                    skip = code[i]
                    if skip:
                        print_("branch", skip, to=i + skip)
                    else:
                        print_(FAILURE)
                i += 1
            elif op in (REPEAT, REPEAT_ONE, MIN_REPEAT_ONE):
                skip, min, max = code[i : i + 3]
                if max == MAXREPEAT:
                    max = "MAXREPEAT"
                print_(op, skip, min, max, to=i + skip)
                dis_(i + 3, i + skip)
                i += skip
            elif op is GROUPREF_EXISTS:
                arg, skip = code[i : i + 2]
                print_(op, arg, skip, to=i + skip)
                i += 2
            elif op in (ASSERT, ASSERT_NOT):
                skip, arg = code[i : i + 2]
                print_(op, skip, arg, to=i + skip)
                dis_(i + 2, i + skip)
                i += skip
            elif op is INFO:
                skip, flags, min, max = code[i : i + 4]
                if max == MAXREPEAT:
                    max = "MAXREPEAT"
                print_(op, skip, bin(flags), min, max, to=i + skip)
                start = i + 4
                if flags & SRE_INFO_PREFIX:
                    prefix_len, prefix_skip = code[i + 4 : i + 6]
                    print_2("  prefix_skip", prefix_skip)
                    start = i + 6
                    prefix = code[start : start + prefix_len]
                    print_2(
                        "  prefix",
                        "[%s]" % ", ".join("%#02x" % x for x in prefix),
                        "(%r)" % "".join(map(chr, prefix)),
                    )
                    start += prefix_len
                    print_2("  overlap", code[start : start + prefix_len])
                    start += prefix_len
                if flags & SRE_INFO_CHARSET:
                    level += 1
                    print_2("in")
                    dis_(start, i + skip)
                    level -= 1
                i += skip
            elif op is NOP:
                print_(op)
            elif op in {ABS_JUMP, LS_BRANCH}:
                to = code[i]
                print_(op, to)
                i += 1
            else:
                raise ValueError(op)

        level -= 1

    dis_(0, len(code))
