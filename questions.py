"""Hand-labelled questions, for measuring retrieval rather than admiring it.

Ten questions a compliance analyst might actually ask, each paired with the
sections that would genuinely answer it.

Two decisions about this list are worth stating.

The expectations are *sets*, not single citations. Several of these questions
have more than one right answer: record retention is stated generally in
§1010.430 and again, specifically for customer identification records, in
§1020.220. Scoring against a single "correct" section would count a correct
retrieval as a miss, and the resulting number would understate the very
improvement it exists to measure.

The questions are written by hand, not generated from the corpus. A question
generated from a section inherits that section's vocabulary, which inflates
recall and makes a before/after comparison meaningless — it measures how well
the retriever matches text against itself.
"""

#: (question, sections that would answer it). Every citation here was read in
#: the cached corpus, not just matched by keyword — keyword matching produced
#: three plausible-looking wrong answers on the first pass. §1010.306 mentions
#: foreign financial accounts but sets a filing *deadline* rather than saying
#: who files; §1022.380 says "money transmitter" inside a registration example
#: rather than defining it; §1010.415 covers monetary instruments, not funds
#: transfers. All three were dropped. A too-generous expectation set inflates
#: recall and lets a bad retrieval score as a hit, which corrupts the only
#: number the README depends on.
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
