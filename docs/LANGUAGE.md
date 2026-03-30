##### \# VoxLang — Language Reference

##### > Voice-first programming language. Every keyword sounds natural when spoken aloud.

##### 

##### \---

##### 

##### \## Variables

##### ```voxlang

##### store 20 into age

##### store "Alice" into name

##### store collection 1 and 2 and 3 and 4 and 5 into numbers

##### store 1 divided by 3 into third precisely

##### ```

##### 

##### \---

##### 

##### \## Output (all aliases work)

##### ```voxlang

##### output age

##### show age

##### tell me age

##### what is age

##### display age

##### print age

##### reveal age

##### ```

##### 

##### \---

##### 

##### \## Input

##### ```voxlang

##### ask what is your name then save into name

##### hear how old are you then save into age

##### question what is your score then save into score

##### ```

##### 

##### \---

##### 

##### \## Update a Value

##### ```voxlang

##### update age to 25

##### change age to 25

##### set age to 25

##### modify age to 25

##### ```

##### 

##### \---

##### 

##### \## Raise / Lower a Value

##### ```voxlang

##### raise score by 10

##### increase score by 10

##### add 10 to score

##### bump up score by 10

##### 

##### lower lives by 1

##### decrease lives by 1

##### subtract 1 from lives

##### drop down lives by 1

##### ```

##### 

##### \---

##### 

##### \## Conditions

##### ```voxlang

##### when age is bigger than 18 then

##### &#x20; output "adult"

##### otherwise

##### &#x20; output "minor"

##### done

##### ```

##### 

##### Condition aliases: `when` / `if` / `suppose` / `check if`

##### Else aliases: `otherwise` / `else` / `if not`

##### 

##### \---

##### 

##### \## Comparisons

##### 

##### | Phrase | Meaning |

##### |---|---|

##### | `is bigger than` | > |

##### | `is smaller than` | < |

##### | `is equal to` | == |

##### | `is not equal to` | != |

##### | `is at least` | >= |

##### | `is at most` | <= |

##### | `is empty` | == \[] or "" |

##### | `is true` | == true |

##### | `is false` | == false |

##### 

##### \---

##### 

##### \## Loops

##### ```voxlang

##### \-- Repeat N times

##### do this 5 times

##### &#x20; output index

##### done

##### 

##### \-- For each

##### go through every item in numbers

##### &#x20; output item

##### done

##### 

##### \-- While

##### keep going while x is bigger than 0

##### &#x20; lower x by 1

##### done

##### ```

##### 

##### Loop aliases: `do this` / `repeat` / `cycle` / `loop`

##### For-each aliases: `go through every` / `walk through every` / `visit every` / `step through every`

##### While aliases: `keep going while` / `stay while` / `continue while` / `repeat while`

##### 

##### \---

##### 

##### \## Functions

##### ```voxlang

##### build greet using name

##### &#x20; output "Hello " joined with name

##### done

##### 

##### use greet with "Alice"

##### store result of greet with "Bob" into greeting

##### ```

##### 

##### Define aliases: `build` / `create` / `make` / `craft` / `define`

##### Call aliases: `use` / `call` / `trigger` / `run` / `activate`

##### 

##### \---

##### 

##### \## Math \& Equations

##### ```voxlang

##### \-- Basic math into a variable

##### store circle area with radius 7 into area

##### store hypotenuse with a 3 and b 4 into hyp

##### store square root of 144 into root

##### store 15 percent of 200 into discount

##### store 2 to the power of 8 into result

##### 

##### \-- Algebra: solve and store

##### solve x where x plus 5 equals 20

##### solve y where 2 times y plus 3 equals 15

##### solve z where z squared plus 4 times z plus 4 equals 0

##### 

##### \-- Precise decimals

##### store 1 divided by 3 into third precisely

##### ```

##### 

##### \---

##### 

##### \## Math Block

##### ```voxlang

##### math block

##### &#x20; store circle area with radius 7 into area

##### &#x20; solve x where x squared plus 4 times x plus 4 equals 0

##### &#x20; store hypotenuse with a 6 and b 8 into diagonal

##### done

##### ```

##### 

##### \---

##### 

##### \## Comments

##### ```voxlang

##### \-- this is a comment

##### note this is a comment

##### remark this is a comment

##### ```

##### 

##### \---

##### 

##### \## Block Closer (all work)

##### ```voxlang

##### done

##### end

##### finish

##### close

##### ```

##### 

##### \---

##### 

##### \## Operator Precedence (PEMDAS)

##### 

##### | Priority | Operation | Example |

##### |---|---|---|

##### | 1 (highest) | Parentheses | `(2 + 3) times 4` |

##### | 2 | Exponents | `2 to the power of 3` |

##### | 3 | Multiply / Divide / Mod | `10 times 2 divided by 4` |

##### | 4 | Add / Subtract | `5 plus 3 minus 1` |

##### | 5 | Shift | `4 shift left 2` |

##### | 6 (lowest) | Comparisons | `x is bigger than 5` |

##### 

##### \---

##### 

##### \## Built-in Functions

##### 

##### | Function | What it does |

##### |---|---|

##### | `length` | Length of list or string |

##### | `reverse` | Reverse a list |

##### | `sum` | Sum all numbers in list |

##### | `max` | Largest item |

##### | `min` | Smallest item |

##### | `text` | Convert to string |

##### | `number` | Convert to number |

##### | `round` | Round to N decimals |

##### | `abs` | Absolute value |

##### | `sqrt` | Square root |

##### | `power` | Exponentiation |

##### | `floor` | Round down |

##### | `ceiling` | Round up |

##### | `factorial` | Factorial |

##### | `sin` | Sine (degrees) |

##### | `cos` | Cosine (degrees) |

##### | `tan` | Tangent (degrees) |

##### | `log` | Logarithm |

##### | `contains` | Check membership |

##### | `join` | Join list to string |

##### | `split` | Split string to list |

##### | `upper` | Uppercase |

##### | `lower` | Lowercase |

##### | `range` | Generate number list |

##### | `random` | Random number |

##### 

##### \---

##### 

##### \## Transparency Panel

##### 

##### When you run code, the right panel shows 4 tabs:

##### 

##### \*\*Tokens\*\* — every token the lexer found with its type and data width

##### \*\*Syntax\*\* — every grammar rule matched during parsing

##### \*\*Semantic\*\* — symbol table with name, type, width, value, scope, and line

##### \*\*Trace\*\* — step-by-step execution log with scope depth and operations

