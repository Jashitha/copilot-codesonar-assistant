---
name: ask-codesonar
description: Ask natural-language questions about CodeSonar findings and tracker status.
---

Answer this CodeSonar question using installed tracker/CSV data:

Question: ${input:question:Ask about owner workload, pending issues, class distribution, priority split, Gerrit review links, or specific IDs}

Steps:
1. Invoke `@CodeSonar-Assistant` with the question.
2. Return a concise answer with exact counts.
3. If there are matches, include the first few relevant findings.
