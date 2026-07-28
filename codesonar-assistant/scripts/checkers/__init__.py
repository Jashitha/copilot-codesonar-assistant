"""
checkers package

Each sub-module is a self-contained checker with a single `run(code: str)`
function.  Import them individually; this package does not aggregate them so
that precommit_review.py stays in explicit control of which checkers run.
"""
