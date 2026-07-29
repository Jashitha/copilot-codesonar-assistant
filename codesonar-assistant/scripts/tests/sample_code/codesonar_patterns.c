#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/*
 * Sample file for codesonar_checker testing.
 * Each function demonstrates a CodeSonar-correlated finding.
 */

/* Use of strcpy → CodeSonar: Use of strcpy, MISRA Rule 21.18 */
void demo_strcpy(const char *src)
{
    char dst[16];
    snprintf(dst, sizeof(dst), "%s", src);          /* HIGH: no size validation */
}

/* Use of sprintf → CodeSonar: Use of sprintf, MISRA Rule 21.6 */
void demo_sprintf(const char *user, const char *msg)
{
    char buf[64];
    snprintf(buf, sizeof(buf), "%s: %s", user, msg);   /* HIGH: no length limit */
}

/* Inappropriate Assignment Type → MISRA Rule 10.3 */
void demo_bad_assign(void)
{
    unsigned int count = -1;    /* HIGH: negative assigned to unsigned */
    (void)count;
}

/* Ignored Return Value → MISRA Rule 17.7 */
void demo_ignored_rv(void)
{
    malloc(64);                 /* MEDIUM: return value not captured */
}

/* Use After Free → MISRA Rule 18.6 */
void demo_use_after_free(void)
{
    char *p = (char *)malloc(32);
    if (p == NULL) return;
    free(p);
    p[0] = 'x';                /* HIGH: use after free */
}

/* Null Test After Dereference → MISRA Rule 18.2 */
void demo_null_after_deref(struct Node *node)
{
    if (node == NULL) {         /* HIGH: null check too late */
        return;
    }
    int val = node->value;      /* dereference before null check */
    (void)val;
}

/* Unreachable Code → MISRA Rule 2.2 */
int demo_unreachable(int x)
{
    return x * 2;
    int unused = 42;            /* MEDIUM: unreachable */
    return unused;
}
