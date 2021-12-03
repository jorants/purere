Purere
======

Purere is a python regex library written fully in python. It compiles regex patterns into a python functions.

This library is still in development, but it passes almost all tests from the cpython testset for `re` (only failing tests involving the few unimplemented parts).
It also works with pypy3.

Why?
----
Mostly curiosity. Building a regex engine is fun, and purere is actually quite fast for a pure python libary. On some rather evil inputs it even outpreforms other backtracking algorithms due to smarter caching (see the Design section below). 

However, having a Python only version of the standard libary can be usefull when porting python to new platforms where we can not use a c compiler.  

Usage
-----

Not in PyPi yet, but after cloning you may
```
pip install .
```

After which your code should work with the drop in replacement
```
import purere as re
```

Development status
------------------
Supported:
- ASCII, Unicode and byte-like strings
- Ignore case mode `I`, multiline mode `M`, and Dot-all mode `M`.
- All character categories: `\d\D\s\S\w\W`. 
- Repetition using `*`, `+`, `?` and `{min,max}`, including non-greedy variants
- All `AT` codes: `$` and `^`, `\A`, `\Z`, `\b`, `\B`
- Non-capturing grouping using `(?:...)`, Capturing groups, group references, conditional matching depending on group ref (e.g. `(?(1)a|b)`) 

Wish-list/known missing:
- Look-back and look-ahead, i.e., the `ASSERT` and `ASSERT_NOT` opcodes.
- Ability to output standalone python code for a pattern that does not require `purere` to run

Will never be implemented:
- The `L` locale flag. Usage is discouraged for `re` and we will not be implementing it. Full unicode support is avalible and sould be used.

Known differences to `re`:
- For Unicode patterns we define `\d` using python's `isnumerical()`, which is not the same behavior as cpython's `re`. To get the original behavior there is an option  `purere.STRICTUNI` that can be passed, in this case `unicodedata` is used to define '\d'.
- We now do not agree with `re` on how to set the group boundaries in `((x|y)*)*` with input string `xyyzz`. Will be fixed in the furture.
- Some minor implementation details:
  - Match objects are not cached and hence copying them gives back a different object, where cpython gives an exact copy for some reason.
  - Buffers containing the bytes that are matched by `finditer` are not locked as pure python code can not do this. In general the behavior of `finditer` on a changing string is undefined and not tested.
  - If a compiled pattern is given to `purere.compile`, as well as flags, then no error is raised. Instead, the pattern is recompiled with the new flags if needed.
  - Debug output shows the generated python code.




Design
------

This library uses backtracking but takes inspiration from finite automata implementations to avoid exponential behavior on certain patterns.
See also Russ Cox their great articles on regex https://swtch.com/~rsc/regexp/ and for a more detailed explanation of this problem.

To avoid re-implementing the parsing of the pattern, the pure python parts of `sre` are reused. In particular, `sre_parse` parses the regex and `sre_compile` compiles it to instructions that would normally be fed to a virtual machine implemented by `_sre.c`. We leave this mostly intact but, slightly get in the middle to refactor the results to fit our needs. This refactoring is done in `proccess.py`. For consistency reasons, compatability with pypy, and to allow us to reimplement the few lines of code from `_sre.c` that are used in `sre_compile.py`, we include a copy of cpythons implementation for their files which have been kept mostly the same. Purere runs fine if the standard libary version is used in cpython.

We do not implement a VM. Instead the resulting code is taken by `compiler.py`. This makes all jump locations absolute jumps and then splits the code into parts such that all jumps are to the beginning of a part. This allows us to number the parts and change the definition of the jumps once again so they reference part numbers. Here some more general parameters are determined as well, like the number of groups, the groups that are back-referenced, and any possible prefixes.

With this in hand python code is generated from the VM code for each of the parts. This is then placed in a big `while True:` loop consisting of many `if part == <some part number>:` statements for the many parts. Some boiler plate code is added and the whole thing is compiled using `exec`. 

Let us now switch to what happens when matching, i.e., in the generated python code. To main variables are present and correspond to the current state of algorithm, the aforementioned `part` denotes the part, and `pos` denotes the position in the string that is being matched.
As we implement a backtracking algorithm, a `stack` is kept of places to jump to if the current branch does not work out, i.e., a list of `(part,pos)` pairs. To ease this jumping back the `while True:` loop sits in another `while stack:` loop. When a `break` occurs in the inner loop a new value is taken from the stack and the inner loop starts again. To avoid double work a set `done` is kept that tracks locations that are already visited as visiting them again will result in the same negative result. A very simple part that only matches the letters a-z might look like:
```python
...
if part = 1:
 if pos>=len(s): break
 if not('a' <= s[pos] <= 'z'): break
 part += 1
...
```

A bit more care needs to be taken to implement capturing groups and their related operations. Simple capture groups are simple enough, we just keep a tuple `marks` that contains all the starting and ending spots and keep this in the stack as well. Note that we do not add this to our definition of `done`, as doing so would make the algorithm visit every possible combination of `marks` for every capturing group, even if many of these lead to the same `part` and `pos` afterwards and hence will have the same negative matching result. An exception to this is when the groups are referenced later with a back-reference, as now the specifics of the `marks` matters for the matching result. For these groups a second tuple `smarks` is kept that is added to the `stack` and to `done`. 

This design leads to a worst-case time complexity `O(p^2s^(1+2c))`, where `p` is the pattern size, `s` is the string length, and `c` is the number of back-referenced groups. Here the second `p` factor comes from the finding of the if for the right part in the big while loop, but in practice this can be ignored as the actual matching inside the if will take longer. This might be sped up in a future version using binary search by nesting the if statements. 

Example result
--------------
As an ilustration of the above, the regex `(cool|awesome)*` is compiled to the following VM code, where jumps are given by line numbers:
```
01: LS_BRANCH [10]
02: MARK 0
03: LS_BRANCH [5]
04: LITERALS [99, 111, 111, 108]
05: ABS_JUMP 9
06: LITERALS [97, 119, 101, 115, 111, 109, 101]
07: ABS_JUMP 9
08: MARK 1
09: ABS_JUMP 1
10: SUCCESS
```
Here the `MARK` codes denote the start and end of groups. The `LS_BRANCH` instructions take a list of lines to branch to (and also step to the next line first), `LITERALS` checks for the existence of a string of characters in the string, and `ABS_JUMP` simply jumps to a line.

This is then compiled into a python function as below. The code is slightly cleaned up to remove parts that are needed in general but do not get used in the simple regex above. Also, note that at this point line numbers have been converted in numbers of parts of the VM code that form a logical block.
```python
def regex(s, pos = 0, endpos = None, full = False):
 # Regex: '(cool|awesome)*'
 endpos = len(s) if endpos is None else min(endpos,len(s))
 marks = (None,)*2
 stack = [(0,pos,marks)]
 while stack:
  part,pos,marks,smarks = stack.pop()
  while (part,pos) in done and stack:
   part,pos,marks = stack.pop()
  if (part,pos) in done:
   break

  while True:
   if part == 0:
    done.add((part,pos))
    stack.append((3,pos,marks))
    # ^  [LS_BRANCH, [3]]
    marks = marks[:0]+ (pos,) +marks[1:]
    # ^  [MARK, 0]
    stack.append((1,pos,marks))
    # ^  [LS_BRANCH, [1]]
    if not(pos+4 <= endpos) or s[pos:pos+4] != 'cool': break
    pos += 4
    # ^  [LITERALS, [99, 111, 111, 108]]
    part = 2
    # ^  [ABS_JUMP, 2]
   
   if part == 1:
    done.add((part,pos))
    if not(pos+7 <= endpos) or s[pos:pos+7] != 'awesome': break
    pos += 7
    # ^  [LITERALS, [97, 119, 101, 115, 111, 109, 101]]
    part = 2
    # ^  [ABS_JUMP, 2]
   
   if part == 2:
    done.add((part,pos))
    marks = marks[:1]+ (pos,) +marks[2:]
    # ^  [MARK, 1]
    part = 0
    continue
    # ^  [ABS_JUMP, 0]
   
   if part == 3:
    done.add((part,pos))
    if ((full and pos == endpos) or not full):
     return True,pos,marks,done
    else:
     break
    # ^  [SUCCESS]
 return None, None, None, done

```

Benchmarking
------------
(Relative) speed will highly depend on the system, python version, and the benchmarks used.
Some benchmarks are included and can be run with pytest to get a rough idea:
```
pytest tests/test_speed.py -rP
```
We get about a factor 10 slowdown in compilation when using CPython (compared to using `re`).
As for matching time, it really depends on the input. We are particulairly slow in two cases:
 - Matching single character repeats like `.*`.
 - Matching huge texts with a regex that does not start with a string prefix (for example `[ab]cd` does not start with a string prefix, while `ab[cd]` starts with the prefix `ab`)

Both cases are slower because searching long inputs with a loop in python can never beat a loop in C. 
However, if the pattern always starts the same, then `find()` is used to only try an match at those positions where the pattern might be. For reasonable patterns the slowdown with CPython is mostly between 6 and 20 times.


Development
-----------

Poetry is used for package management. Apart from that, only pytest is needed to run the tests and there are no runtime dependencies. 
To install pytest and setup a virtual envoirment run `poetry install`.
To run the tests run `poetry run pytest`.

Name
----
The name is a reference to the pure python nature and the Dutch word for 'to mash' (which is what my head feels like when I work with regex).


