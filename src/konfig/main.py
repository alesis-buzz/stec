from lark import Lark
from rich import print

grammar = Lark("""
?start: expressions*
?expressions: expose_expr | variable_expr

?values: NUMBER | STRING | FLOAT | BOOL
       | VARIABLE | if_expr   

?types: "int" -> integer_type
      | "string" -> string_type
      | "bool" -> bool_type
      | "float" -> float_type

expose_expr: "expose" types NAME "=" values
variable_expr: "var" NAME "=" values

if_expr: values "?" values ":" values

%import common.WS
%import common.NUMBER
%import common.ESCAPED_STRING -> STRING
%import common.CNAME -> NAME
%ignore WS

BOOL: "true" | "false"
FLOAT: NUMBER "." NUMBER
VARIABLE: "$"NAME
""")

parsed = grammar.parse("""
var dev = true

expose int port = 8080
expose string secret = "secreteetoiertoiertoeritoeritoeriotio"

expose string url = $dev ? "127.0.0.1" : "0.0.0"
""")

print(parsed)