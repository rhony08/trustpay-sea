"""Scam Vaccine quiz (Phase 3B.5) — 3 archetype scenarios → Anti-Scam Aware badge."""

from __future__ import annotations

from app.config import get_settings

_QUESTIONS = [
    {
        "id": "q1",
        "archetype": "FAKE_JOB",
        "scenario": "A recruiter offers a high-paying job but asks you to pay a "
        "training deposit before the interview.",
        "options": [
            "Pay it quickly to secure the role",
            "Refuse — legitimate employers never charge you to be hired",
            "Ask a friend to pay on your behalf",
        ],
        "answer": 1,
    },
    {
        "id": "q2",
        "archetype": "INVESTMENT_PIG_BUTCHERING",
        "scenario": "An investment app shows big profits but says you must deposit "
        "more before you can withdraw.",
        "options": [
            "Deposit more to unlock the withdrawal",
            "Take a loan to deposit faster",
            "Stop — requiring deposits to withdraw is a classic scam",
        ],
        "answer": 2,
    },
    {
        "id": "q3",
        "archetype": "PHISHING_PRETEXTING",
        "scenario": "You get an SMS: 'Your bank account is suspended, share the OTP "
        "to reactivate it now.'",
        "options": [
            "Share the OTP to reactivate the account",
            "Never share OTP — open your bank app directly to check",
            "Reply asking for more details",
        ],
        "answer": 1,
    },
]


def public_questions() -> list[dict]:
    return [
        {
            "id": q["id"],
            "archetype": q["archetype"],
            "scenario": q["scenario"],
            "options": q["options"],
        }
        for q in _QUESTIONS
    ]


def grade(answers: list[int]) -> tuple[int, bool]:
    correct = 0
    for index, question in enumerate(_QUESTIONS):
        if index < len(answers) and answers[index] == question["answer"]:
            correct += 1
    return correct, correct >= get_settings().quiz_pass_threshold
