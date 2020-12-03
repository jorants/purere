Purere
======

Purere is a python regex libary written fully in python without any standard libary dependencies.
This libary is in early development, and has been worded on for only two days.
The eventual goal is to be a drop-in replacement for re.

Suported:
- Matching ASCII strings
- Charcter groups using `[` and `]`
- Escape sequences 
- Non-capturing grouping using `(?:...)`
- Repetition using `*`, `+`, `?` and `{min,max}`
- `$` and `^`
- Capturing groups 

Wishlist:
- Setting of options like ASCII or IGNORECASE
- Interface similair to python's `re`
- Suport for `\A`, `\Z`, `\b`, `\B`
- Lookback and lookahead
 
Will never be implemented:
- Back-references to matched groups. Since purere uses a automata aprouch to matching this is infeasable. Also, this is an NP-complete problem and should be avoided.


Design
------

Highly inspired by Russ Cox theeir articles on regex: https://swtch.com/~rsc/regexp/
The libary uses an automata algorithm, instead of the widely used backtracking.
This ensures that the algorithm runs in linear time.
In particular, the runtime of a regex without these will be `O(s p)`, where `s` is the length of the string to be matched against and `p` is the length of the pattern.


Development
-----------

Poetry is used for package mangement. Apart from that only pytest is needed to run the tests. 
To install pytest and setup a virtual enviorment run `poetry install`.
To run the tests run `poetry run pytest`.

Name
----
The name is a reference to the pure python nature and the Duch word for 'to mash' (which is what my head feels like when i work with regex).


