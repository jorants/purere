import re
import purere

def test_multiline():
    purere.compile(r"(?m:^)")

def test_multiplication_bug():
    purere.compile(r"(?:ab*)*")


tokenizer_re = r"""(?P<IGNORE>(?:[ \f\t]+)(?:#[^\r\n]*)?\r?\n|(?:[ \f\t]+)?(?:#[^\r\n]*)\r?\n|(?!^)(?:[ \f\t]+))|(?P<INDENTATION>^(?:[ \f\t]+)(?!$))|(?P<NAME>(?:(?=\D)\w+))|(?P<NUMBER>(?:[0-9](?:_?[0-9])*[jJ]|(?:(?:(?:[0-9](?:_?[0-9])*\.(?:[0-9](?:_?[0-9])*)?|\.[0-9](?:_?[0-9])*)(?:[eE][-+]?[0-9](?:_?[0-9])*)?)|(?:[0-9](?:_?[0-9])*(?:[eE][-+]?[0-9](?:_?[0-9])*)))[jJ])|(?:(?:(?:[0-9](?:_?[0-9])*\.(?:[0-9](?:_?[0-9])*)?|\.[0-9](?:_?[0-9])*)(?:[eE][-+]?[0-9](?:_?[0-9])*)?)|(?:[0-9](?:_?[0-9])*(?:[eE][-+]?[0-9](?:_?[0-9])*)))|(?:(?:0[xX](?:_?[0-9a-fA-F])+)|(?:0[bB](?:_?[01])+)|(?:0[oO](?:_?[0-7])+)|(?:(?:0(?:_?0)*|[1-9](?:_?[0-9])*))))|(?P<STRING>(?:(?i:[bruf]|br|fr|rb|rf)?)(?:(?:['](?:(?:[^\n'\\]|\\.)*)['])|(?:["](?:(?:[^\n"\\]|\\.)*)["])|(?:[']{3}(?:(?:[^\\]|\\.)*?)[']{3})|(?:["]{3}(?:(?:[^\\]|\\.)*?)["]{3})))|(?P<NEWLINE>\r?\n)|(?P<OP>(?:<<=)|(?:>>=)|(?:\*\*=)|(?:\.\.\.)|(?://=)|(?:@=)|(?:\->)|(?://)|(?:==)|(?:!=)|(?:<=)|(?:>=)|(?:<<)|(?:>>)|(?:\*\*)|(?:\+=)|(?:\-=)|(?:\*=)|(?:/=)|(?:%=)|(?:\&=)|(?:\|=)|(?:\^=)|(?::=)|(?:\~)|(?:\^)|(?:@)|(?:\()|(?:\))|(?:\[)|(?:\])|(?::)|(?:,)|(?:;)|(?:\+)|(?:\-)|(?:\*)|(?:/)|(?:\|)|(?:\&)|(?:<)|(?:>)|(?:=)|(?:\.)|(?:%)|(?:\{)|(?:\}))|(?P<AWAIT>async)|(?P<ASYNC>await)"""


code = """
if x == 5.0:
    # does something
    print("Hello")

"""

def test_tokenizer_bug():
    pat = purere.compile(tokenizer_re,purere.M)
    sc = pat.scanner(code)
    while True:
        m = sc.match()
        if m == None:
            break
        # d = {k:v for k,v in m.groupdict().items() if v != None}
        # name = next(iter(d.keys()))
        # val =m.group()
        # if name == "IGNORE":
        #     continue
        # elif name == "INDENTATION":
        #     indent = len(val.replace("\t"," "*8))
        #     if indent > indentstack[-1]:
        #         print("INDENT",repr(val))
        #         continue
        #     while indentstack and indent < indentstack[-1]:
        #         print("INDENT",repr(" "*(indentstack[-1]-indent)))
        #         indentstack.pop()
        # else:
        #     print(name,repr(val))

