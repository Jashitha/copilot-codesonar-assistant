# ---------------------------------------------------------------------------
# FIX_GUIDE  — rich, three-level fix guidance per issue class
#
# Keys per entry:
#   description  – one-sentence explanation of what CodeSonar is flagging
#   causes       – list of typical root causes
#   bad_code     – minimal bad-code snippet (string, C/C++)
#   good_code    – corrected snippet (string, C/C++)
#   checklist    – list of "things to check" questions (plain text)
#   standards    – list of relevant standards
# ---------------------------------------------------------------------------
FIX_GUIDE: dict[str, dict] = {

    "Inappropriate Assignment Type": {
        "description": (
            "The value being assigned cannot be safely represented by the "
            "destination type — possible truncation, sign change, or precision loss."
        ),
        "causes": [
            "Signed → Unsigned assignment",
            "Unsigned → Signed assignment",
            "64-bit → 32-bit narrowing",
            "Integer → Enum coercion",
            "Integer ↔ Pointer cast",
            "Float → Integer truncation",
        ],
        "bad_code": (
            "uint8_t len;\n"
            "int size = get_size();\n"
            "len = size;  /* truncates / loses sign */\n"
        ),
        "good_code": (
            "uint8_t len;\n"
            "int size = get_size();\n"
            "if ((size >= 0) && (size <= UINT8_MAX))\n"
            "{\n"
            "    len = (uint8_t)size;\n"
            "}\n"
            "else\n"
            "{\n"
            "    /* handle error */\n"
            "}\n"
        ),
        "checklist": [
            "Is the cast hiding an overflow?",
            "Can the value become negative?",
            "Is precision lost?",
            "Should the variable type be changed instead?",
        ],
        "standards": ["MISRA C 2012", "CERT C INT31-C", "AUTOSAR A5-0-3"],
    },

    "Buffer Overrun": {
        "description": (
            "A write operation goes past the end of an allocated buffer, "
            "potentially corrupting adjacent memory."
        ),
        "causes": [
            "Missing or incorrect bounds check before write",
            "Off-by-one error in loop limit",
            "Untrusted input used as copy length",
            "Unsafe functions: strcpy, sprintf, gets",
        ],
        "bad_code": (
            "char buf[8];\n"
            "strcpy(buf, user_input);  /* no length check */\n"
        ),
        "good_code": (
            "char buf[8];\n"
            "snprintf(buf, sizeof(buf), \"%s\", user_input);\n"
        ),
        "checklist": [
            "Is the destination size validated before every write?",
            "Are loop bounds tight (< not <=)?",
            "Is input length capped to buffer capacity?",
            "Can you replace unsafe functions with bounded equivalents?",
        ],
        "standards": ["MISRA C 2012 Rule 21.6", "CERT C ARR38-C", "CWE-122"],
    },

    "Buffer Underrun": {
        "description": (
            "A read or write occurs before the start of a buffer, "
            "causing undefined behaviour."
        ),
        "causes": [
            "Negative array index due to signed arithmetic",
            "Pointer decremented past base",
            "Off-by-one in reverse iteration",
        ],
        "bad_code": (
            "int arr[10];\n"
            "int idx = get_idx();  /* may return negative */\n"
            "arr[idx] = 0;         /* underrun if idx < 0 */\n"
        ),
        "good_code": (
            "int arr[10];\n"
            "int idx = get_idx();\n"
            "if ((idx >= 0) && (idx < 10))\n"
            "{\n"
            "    arr[idx] = 0;\n"
            "}\n"
        ),
        "checklist": [
            "Can the index or pointer become negative?",
            "Are all pointer decrements guarded?",
            "Is the lower bound (0 / base address) checked?",
        ],
        "standards": ["CERT C ARR30-C", "CWE-124"],
    },

    "Use After Free": {
        "description": (
            "Memory is accessed through a pointer after the pointed-to object "
            "has been freed, leading to undefined behaviour."
        ),
        "causes": [
            "Pointer not set to NULL after free()",
            "Shared/aliased pointer still used after one path frees it",
            "Object freed inside a callback while caller still holds a reference",
        ],
        "bad_code": (
            "char *p = malloc(64);\n"
            "free(p);\n"
            "p[0] = 'x';  /* use after free */\n"
        ),
        "good_code": (
            "char *p = malloc(64);\n"
            "free(p);\n"
            "p = NULL;    /* prevent accidental reuse */\n"
        ),
        "checklist": [
            "Is the pointer set to NULL immediately after free()?",
            "Are there aliases (other pointers to the same allocation)?",
            "Is the object lifetime clear at every call site?",
        ],
        "standards": ["CERT C MEM30-C", "CWE-416", "MISRA C 2012 Rule 22.2"],
    },

    "Null Test After Dereference": {
        "description": (
            "A pointer is dereferenced before the NULL check that guards it, "
            "making the check ineffective."
        ),
        "causes": [
            "NULL guard placed after the dereference instead of before",
            "Compiler re-orders a check that came logically after a dereference",
            "Code refactoring moved the dereference above its guard",
        ],
        "bad_code": (
            "int val = p->field;  /* dereference first */\n"
            "if (p == NULL) { return; }  /* check too late */\n"
        ),
        "good_code": (
            "if (p == NULL) { return; }  /* check first */\n"
            "int val = p->field;\n"
        ),
        "checklist": [
            "Does the NULL check appear before every dereference?",
            "Is there an early-return / assert before use?",
            "Can the pointer ever be NULL at this call site?",
        ],
        "standards": ["CERT C EXP34-C", "CWE-476"],
    },

    "Use of strcpy": {
        "description": (
            "strcpy() copies bytes until a NUL terminator with no length limit, "
            "overflowing the destination if the source is longer."
        ),
        "causes": [
            "Direct use of strcpy() on user-supplied or external strings",
            "Copy destination size not accounted for",
        ],
        "bad_code": (
            "char dst[32];\n"
            "strcpy(dst, src);  /* no bounds check */\n"
        ),
        "good_code": (
            "char dst[32];\n"
            "snprintf(dst, sizeof(dst), \"%s\", src);\n"
            "/* or: strncpy(dst, src, sizeof(dst) - 1); dst[sizeof(dst)-1] = '\\0'; */\n"
        ),
        "checklist": [
            "Is the destination buffer large enough for the longest possible source?",
            "Is NUL-termination guaranteed after the copy?",
            "Can snprintf / strlcpy replace strcpy here?",
        ],
        "standards": ["CERT C STR31-C", "MISRA C 2012 Rule 21.6", "CWE-120"],
    },

    "Use of strcmp": {
        "description": (
            "strcmp() assumes both arguments are valid NUL-terminated strings; "
            "passing a non-terminated or NULL pointer causes undefined behaviour."
        ),
        "causes": [
            "Input string not validated before comparison",
            "NULL pointer passed to strcmp()",
            "Non-terminated character array used as argument",
        ],
        "bad_code": (
            "if (strcmp(user_str, \"admin\") == 0) { /* ... */ }\n"
            "/* user_str may be NULL or unterminated */\n"
        ),
        "good_code": (
            "if ((user_str != NULL) && (strcmp(user_str, \"admin\") == 0)) { /* ... */ }\n"
        ),
        "checklist": [
            "Is the string pointer validated as non-NULL?",
            "Is the string guaranteed to be NUL-terminated?",
            "Should strncmp() be used to limit comparison length?",
        ],
        "standards": ["CERT C STR32-C", "CWE-170"],
    },

    "Cast Alters Value": {
        "description": (
            "A cast changes the numeric value of the expression, not merely its type, "
            "indicating a potential data-integrity issue."
        ),
        "causes": [
            "Casting a wider type to a narrower one (truncation)",
            "Casting a signed negative to unsigned",
            "Float-to-integer truncation",
        ],
        "bad_code": (
            "uint32_t big = 0x12345678U;\n"
            "uint8_t  small = (uint8_t)big;  /* 0x78 — value changed */\n"
        ),
        "good_code": (
            "uint32_t big = 0x12345678U;\n"
            "if (big <= UINT8_MAX)\n"
            "{\n"
            "    uint8_t small = (uint8_t)big;\n"
            "}\n"
        ),
        "checklist": [
            "Is the value range of the source bounded to fit the target type?",
            "Is the cast intentional and documented?",
            "Should the variable type be widened instead?",
        ],
        "standards": ["MISRA C 2012 Rule 10.3", "CERT C INT02-C"],
    },

    "Cast Removes const Qualifier": {
        "description": (
            "A cast discards a const qualifier, allowing modification of data "
            "that was intended to be read-only."
        ),
        "causes": [
            "Passing a const pointer to a function that takes a non-const pointer",
            "Legacy API incompatibility",
            "Incorrect use of (void *) casts",
        ],
        "bad_code": (
            "void process(char *buf) { /* modifies buf */ }\n"
            "const char *data = \"hello\";\n"
            "process((char *)data);  /* casts away const */\n"
        ),
        "good_code": (
            "void process(const char *buf) { /* read-only */ }\n"
            "const char *data = \"hello\";\n"
            "process(data);\n"
        ),
        "checklist": [
            "Can the called function be changed to accept a const pointer?",
            "Is the underlying data actually modified after the cast?",
            "Is a local mutable copy the right solution?",
        ],
        "standards": ["MISRA C 2012 Rule 11.8", "CERT C EXP05-C"],
    },
}

# ---------------------------------------------------------------------------
# ISSUE_EXPLANATIONS  — legacy simple lookup (kept for backward compat)
# ---------------------------------------------------------------------------
ISSUE_EXPLANATIONS = {

    "Use of strcpy": {
        "why": "strcpy() copies data without checking the destination buffer size.",
        "risk": "Can cause buffer overflow, memory corruption and security vulnerabilities.",
        "fix": "Use strncpy(), snprintf(), or another bounded copy function."
    },

    "Use of strcmp": {
        "why": "strcmp() assumes both strings are null-terminated.",
        "risk": "May read beyond valid memory if strings are malformed.",
        "fix": "Validate input strings before comparison."
    },

    "Buffer Overrun": {
        "why": "Writing beyond the end of a buffer.",
        "risk": "Can corrupt memory or lead to crashes and exploits.",
        "fix": "Validate array bounds before every write."
    },

    "Buffer Underrun": {
        "why": "Reading or writing before the start of a buffer.",
        "risk": "Undefined behavior and possible crashes.",
        "fix": "Validate indexes and pointer arithmetic."
    },

    "Use After Free": {
        "why": "Memory is accessed after it has been freed.",
        "risk": "Undefined behavior, crashes, and exploitable vulnerabilities.",
        "fix": "Set pointers to NULL after free() and avoid accessing freed memory."
    },

    "Null Test After Dereference": {
        "why": "Pointer is dereferenced before checking whether it is NULL.",
        "risk": "Possible segmentation fault.",
        "fix": "Perform the NULL check before dereferencing."
    },

    "Inappropriate Assignment Type": {
        "why": "Assignment converts between incompatible data types.",
        "risk": "Possible data loss or unexpected behavior.",
        "fix": "Use explicit casts only when safe, or change variable types."
    },

    "Conversion to Function Pointer": {
        "why": "Converting data pointers to function pointers is not portable.",
        "risk": "Undefined behavior.",
        "fix": "Avoid casting data pointers to function pointers."
    },

    "Conversion from Function Pointer": {
        "why": "Converting function pointers to object pointers is implementation dependent.",
        "risk": "Undefined behavior.",
        "fix": "Avoid pointer type conversions."
    },

    "Function Pointer Conversion": {
        "why": "Function pointer type conversion may be unsafe.",
        "risk": "Calling through an incompatible function pointer can crash.",
        "fix": "Use the correct function pointer type."
    }
}