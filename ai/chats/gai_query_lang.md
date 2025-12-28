## User
Can you help me write an EBNF grammar for a new query language I am writing?
+ The language should use strings as filters (ex: "foobar" to match any target containing "foobar").
+ It should support the "AND" / "OR" / and "()" constructs.
+ It should support prefixing string filters with ! to indicate that they are meant to be negative matches (ex: !"foobar").
+ For example, the `"foobar" and : ("foobar" AND !"bazbuz") OR "fatpig"` query would match any targets that match one of the following conditions: (1) the target contains the string "foobar" and does NOT contain the string "bazbuz" (2) the target contains "fatpig"

## Agent
Here’s a clean EBNF that matches what you described (string filters, `AND`/`OR`, parentheses, and `!` for negative string matches), with the usual precedence:

* `!` (NOT) binds tightest
* `AND` next
* `OR` loosest
* parentheses override precedence

```ebnf
(* ======== Top level ======== *)

query      = ws?, or_expr, ws? ;

or_expr    = and_expr, { ws, or_op,  ws, and_expr } ;
and_expr   = unary_expr, { ws, and_op, ws, unary_expr } ;

unary_expr = { ws, "!" }, ws, primary ;

primary    = string
           | "(", ws?, or_expr, ws?, ")" ;

(* ======== Operators (case-insensitive at the lexer level) ======== *)

and_op     = "AND" | "and" | "And" | "aNd" | "anD" | "ANd" | "aND" | "AnD" ;
or_op      = "OR"  | "or"  | "Or"  | "oR" ;

(* If you already have a case-insensitive tokenizer, you can simplify:
   and_op = "AND" ;  or_op = "OR" ;
*)

(* ======== Strings ======== *)

string     = '"', { string_char }, '"' ;

string_char = escape
            | ? any character except `"` and `\` ? ;

escape     = "\", ( "\" | '"' | "n" | "r" | "t" ) ;

(* ======== Whitespace ======== *)

ws         = { " " | "\t" | "\r" | "\n" } ;
```

### How it parses your example intent

For the (corrected) example:

* `"foobar" AND ("foobar" AND !"bazbuz") OR "fatpig"`

This grammar parses it as:

* `(("foobar" AND ("foobar" AND !"bazbuz")) OR "fatpig")`

Which corresponds to:

1. target contains `"foobar"` and does **not** contain `"bazbuz"` (the extra `"foobar"` inside the parens is redundant but allowed)
2. **or** target contains `"fatpig"`

### Notes / easy tweaks

* If you want `!` to apply **only** to string filters (not parenthesized groups), change `unary_expr` to:

  ```ebnf
  unary_expr = [ "!" ], ws?, string
             | primary ;
  ```

  (But most query languages eventually want `!("a" OR "b")`, so the more general unary form is usually nicer.)
* Your sample has an `and : (` in it. Since `:` wasn’t in the requirements, the grammar above doesn’t include it. If `:` is meant to be an optional separator/token, tell me what it’s supposed to mean and I’ll fold it in cleanly.

If you tell me whether you want case-insensitive keywords at the lexer level, and whether you want to allow implicit `AND` (e.g., `"a" "b"`), I can tighten this into a production-ready spec.
