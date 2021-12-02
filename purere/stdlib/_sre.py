# Stub file to make sre_compile and sre_constants happy
MAXGROUPS = 2147483647
MAXREPEAT = 4294967295 
MAGIC = 20171005 # current value
CODESIZE = 4 # in bytes

def unicode_iscased(ch):
    return ch != chr(ch).upper() or ch!= chr(ch).lower()

def unicode_tolower(ch):
    return ord(chr(ch).lower())

def ascii_iscased(ch):
    return ch < 128 and chr(ch).isalpha()

def ascii_tolower(ch):
    return ord(chr(ch).lower())
