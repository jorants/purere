Purere
======

Purere is a python regex library written fully in python.
It replaces the `_sre.c` part of the python SRE regex engine, while still using the `sre_*.py` parts of the library and having an interface compatible with `re`. Patterns are compiled to python code.

This library is in early development, but it passes almost all tests from cpython for the parts that are there.
The tests that do not pass all have to do with the TODOs below.

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

Known differences:
- For Unicode patterns `\d` is defined using python's `isnumerical()`, which is not the same behavior as `re`. To get the original behavior `unicodedata` might be used as an optional dependency by passing the `purere.STRICTUNI` flag.
- We now do not agree with `re` on how to set the group boundaries in `((x|y)*)*` with input string `xyyzz`. Will be fixed in the furture.
- Some implementation details:
  - Match objects are not cached and hence copying them gives back a different object
  - Buffers containing the bytes that are matched by `finditer` are not locked as pure python code can not do this. In general the behavior of `finditer` on a changing string is undefined and not tested.
  - If a compiled pattern is given to `purere.compile` as well as flags then no error is raised. Instead, the pattern is recompiled with the new flags if needed.
  - Debug output now shows python code


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

Design
------

This library uses backtracking but takes inspiration from finite automata implementations to avoid exponential behavior on certain patterns.
See also Russ Cox their great articles on regex https://swtch.com/~rsc/regexp/ and for a more detailed explanation of this problem.

To avoid re-implementing the parsing of the pattern, the pure python parts of `sre` are reused. In particular, `sre_parse` parses the regex and `sre_compile` compiles it to instructions that would normally be fed to a virtual machine implemented by `_sre.c`. We leave this mostly intact but, slightly get in the middle to refactor the results to fit our needs. This refactoring is done in `proccess.py` 

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


Development
-----------

Poetry is used for package management. Apart from that only pytest is needed to run the tests. 
To install pytest and setup a virtual endowment run `poetry install`.
To run the tests run `poetry run pytest`.

Name
----
The name is a reference to the pure python nature and the Dutch word for 'to mash' (which is what my head feels like when I work with regex).


