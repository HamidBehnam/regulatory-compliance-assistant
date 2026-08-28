"""Hand-labelled questions, for measuring retrieval rather than admiring it.

Expectations are sets, not single citations: record retention is stated
generally in §1010.430 and again, for customer identification records, in
§1020.220, and scoring against one "correct" section would count a correct
retrieval as a miss.

The questions are written by hand rather than generated from the corpus. A
generated question inherits its source section's vocabulary, which inflates
recall and makes a before/after comparison a measure of text matching itself.
"""

# Every citation here was read in the cached corpus, not matched by keyword.
# Keyword matching produced three plausible wrong answers on the first pass —
# §1010.306 sets an FBAR filing deadline rather than saying who files,
# §1022.380 says "money transmitter" inside a registration example rather than
# defining it, and §1010.415 covers monetary instruments rather than funds
# transfers — and all three were dropped. A too-generous expectation set lets a
# bad retrieval score as a hit.
QUESTIONS: tuple[tuple[str, frozenset[str]], ...] = (
    (
        "What is the SAR filing threshold for a money services business?",
        frozenset({"1022.320"}),
    ),
    (
        "What is the SAR filing threshold for a bank?",
        frozenset({"1020.320"}),
    ),
    (
        "What identifying information must a bank obtain before opening an account?",
        frozenset({"1020.220"}),
    ),
    (
        "How is a money transmitter defined?",
        frozenset({"1010.100"}),
    ),
    (
        "How long must customer identification records be retained?",
        frozenset({"1010.430", "1020.220"}),
    ),
    (
        "What records must a bank keep of funds transfers of $3,000 or more?",
        frozenset({"1020.410", "1010.410"}),
    ),
    (
        "Who must file a report of foreign bank and financial accounts?",
        frozenset({"1010.350"}),
    ),
    (
        (
            "What are the anti-money laundering program requirements for a "
            "money services business?"
        ),
        frozenset({"1022.210"}),
    ),
    (
        (
            "What are the recordkeeping requirements for the purchase of "
            "monetary instruments over $3,000?"
        ),
        frozenset({"1010.415"}),
    ),
    (
        "What are the beneficial ownership requirements for legal entity customers?",
        frozenset({"1010.230"}),
    ),
)
