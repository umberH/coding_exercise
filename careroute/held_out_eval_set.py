"""A genuinely held-out recall eval set for CareRoute's risk flags.

PROBLEM_STATEMENT.md's recall target is explicit: "Hardship/vulnerability/
scam recall (held-out) >= 0.90." `tests/golden_set.py` is NOT that set - its
own docstring says so ("this is a small regression contract... not the
larger labelled eval set that PROBLEM_STATEMENT.md's recall targets are
measured against"). Reusing it for recall measurement checks that the
`rules` provider still matches patterns it was built to match; it says
nothing about generalization to phrasing nobody wrote the patterns for.

This module's 9 cases (3 per risk flag) were written to avoid every literal
trigger word `careroute/providers/rules.py`'s patterns key on (no
"hardship", "struggl*", "vulnerab*", "scam*", "fraud*", "elderly",
"confus*", "otp", ...) while still describing a real customer situation a
human reader would unambiguously flag. Measured recall here is far lower
than on the golden set - see README.md and DESIGN.md for why that's a
genuine finding about the `rules` provider's limits, not a bug in this set,
and why `careroute eval` reports it as informational rather than gating CI
on it.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class HeldOutCase:
    id: str
    text: str
    expected_hardship: bool
    expected_vulnerability: bool
    expected_scam: bool


HELD_OUT_CASES: tuple[HeldOutCase, ...] = (
    HeldOutCase(
        id="hardship_mortgage_payday_gap",
        text=(
            "The mortgage repayment is due Friday and there's nothing left in my "
            "account until payday - could we push it back a week?"
        ),
        expected_hardship=True,
        expected_vulnerability=False,
        expected_scam=False,
    ),
    HeldOutCase(
        id="hardship_choosing_which_bill",
        text=(
            "I had to choose between the electricity bill and the car "
            "registration this month, is there any flexibility on the due date?"
        ),
        expected_hardship=True,
        expected_vulnerability=False,
        expected_scam=False,
    ),
    HeldOutCase(
        id="hardship_reduced_hours",
        text=(
            "Work cut my hours in half since September so I'm behind on two "
            "of the last three repayments."
        ),
        expected_hardship=True,
        expected_vulnerability=False,
        expected_scam=False,
    ),
    HeldOutCase(
        id="vulnerability_father_repeats_calls",
        text=(
            "My father keeps calling asking about the same transfer over and "
            "over, he gets mixed up about what he's already sent."
        ),
        expected_hardship=False,
        expected_vulnerability=True,
        expected_scam=False,
    ),
    HeldOutCase(
        id="vulnerability_manages_sisters_banking",
        text=(
            "I look after my sister's banking - she has dementia and agreed to "
            "something over the phone yesterday that she shouldn't have."
        ),
        expected_hardship=False,
        expected_vulnerability=True,
        expected_scam=False,
    ),
    HeldOutCase(
        id="vulnerability_post_surgery_medication",
        text=(
            "Keeping track of my accounts has been really hard since my "
            "surgery, the medication makes everything foggy."
        ),
        expected_hardship=False,
        expected_vulnerability=True,
        expected_scam=False,
    ),
    HeldOutCase(
        id="scam_caller_posing_as_security_team",
        text=(
            "A man rang saying he worked for my bank's security team and "
            "asked me to read him the numbers off my card so he could verify it."
        ),
        expected_hardship=False,
        expected_vulnerability=False,
        expected_scam=True,
    ),
    HeldOutCase(
        id="scam_parcel_delivery_link",
        text=(
            "I clicked a link in a text about a parcel delivery and now "
            "there's a payment on my account I don't recognise."
        ),
        expected_hardship=False,
        expected_vulnerability=False,
        expected_scam=True,
    ),
    HeldOutCase(
        id="scam_impersonating_daughter",
        text=(
            "Someone messaged me pretending to be my daughter, asking me to "
            "transfer money urgently for an emergency."
        ),
        expected_hardship=False,
        expected_vulnerability=False,
        expected_scam=True,
    ),
)
