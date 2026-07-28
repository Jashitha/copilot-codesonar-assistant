#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/*
 * Sample file for pre-commit review testing.
 * Contains intentional uses of dangerous APIs.
 */

void copy_username(const char *username)
{
    char buf[64];
    strcpy(buf, username);       /* HIGH: no bounds check */
    printf("User: %s\n", buf);
}

void build_message(const char *user, const char *msg)
{
    char result[128];
    sprintf(result, "%s: %s", user, msg);   /* HIGH: no length limit */
    strcat(result, "\n");                   /* HIGH: no bounds check */
    puts(result);
}

int parse_value(const char *input)
{
    int n   = atoi(input);       /* MEDIUM: no error detection */
    double d = atof(input);      /* MEDIUM: no error detection */
    return n + (int)d;
}

void tokenise(char *csv)
{
    char *tok = strtok(csv, ","); /* MEDIUM: not re-entrant */
    while (tok != NULL) {
        printf("token: %s\n", tok);
        tok = strtok(NULL, ",");
    }
}

void read_input(void)
{
    char buf[32];
    gets(buf);                   /* HIGH: removed from C11 */
    printf("Input: %s\n", buf);
}
