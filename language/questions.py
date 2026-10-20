from django.core import signing

from . import models

# Labels the signature, so a token signed for answers is never accepted anywhere else.
ANSWER_TOKEN_SALT = "language.questions.answer"  # noqa: S105
ANSWER_TOKEN_MAX_AGE = 24 * 60 * 60  # seconds


class InvalidTokenError(Exception):
    """The answer token was changed, has expired, or belongs to another lesson."""


QUESTION_MAPPING = {
    models.Kind.CHARACTER: [
        ("text_to_transliteration", "text", "transliteration"),
        ("transliteration_to_text", "transliteration", "text"),
    ],
    models.Kind.WORD: [
        ("text_to_meaning", "text", "meaning"),
        ("meaning_to_text", "meaning", "text"),
    ],
}


def display(item, side):
    return {
        "main": getattr(item, side),
        "sub": item.transliteration
        if side == "text" and item.kind == models.Kind.WORD
        else "",
    }


def candidate_items(lesson):
    """Every item a question in this lesson may use: same course, this or an earlier lesson."""

    return list(
        models.Item.objects.filter(
            lesson__course=lesson.course_id, lesson__order__lte=lesson.order
        )
    )


def build_question(item, candidates, rng):
    """One question about `item`, or None when no question can be made for it."""
    question_types = QUESTION_MAPPING.get(item.kind)
    if not question_types:
        return None

    question_type, prompt_side, answer_side = rng.choice(question_types)
    prompt = display(item, prompt_side)
    correct = display(item, answer_side)
    if not prompt["main"] or not correct["main"]:
        return None

    # A new list, so shuffling it does not reorder `candidates` for later questions.
    # Get others from candidate set so that we can select wrong answer pool.
    others = [c for c in candidates if c.kind == item.kind and c.id != item.id]
    rng.shuffle(others)

    # Build options: three wrong and the already selected correct one
    # No two options may read the same, and an empty label is never an option.
    seen = {"", correct["main"]}
    wrong = []
    for other in others:
        option = display(other, answer_side)
        if option["main"] in seen:
            continue
        seen.add(option["main"])
        wrong.append(option)
        if len(wrong) == 3:
            break

    if not wrong:
        return None

    options = [*wrong, correct]
    rng.shuffle(options)
    return {
        "item": item,
        "type": question_type,
        "prompt": prompt,
        "options": options,
        "answer": options.index(correct),
    }


def build_questions(lesson, rng):
    """One question for each item in the lesson that can have one, in random order."""
    candidates = candidate_items(lesson)
    questions = []
    for item in candidates:
        if item.lesson_id != lesson.id:
            continue
        question = build_question(item, candidates, rng)
        if question is not None:
            questions.append(question)
    rng.shuffle(questions)
    return questions


def public_question(question, lesson):
    """What the browser may see: the answer travels only inside the signed token."""
    token = signing.dumps(
        {
            "lesson": lesson.id,
            "item": question["item"].id,
            "answer": question["answer"],
        },
        salt=ANSWER_TOKEN_SALT,
    )
    return {
        "token": token,
        "type": question["type"],
        "prompt": question["prompt"],
        "options": question["options"],
    }


def check_answer(token, lesson_id, choice):
    """Compare `choice` with the answer sealed in `token`."""
    try:
        data = signing.loads(
            token, salt=ANSWER_TOKEN_SALT, max_age=ANSWER_TOKEN_MAX_AGE
        )
    except signing.BadSignature as error:
        # SignatureExpired is a subclass, so old tokens land here too.
        raise InvalidTokenError from error

    # A valid token from another lesson must not be accepted here.
    if data["lesson"] != lesson_id:
        raise InvalidTokenError

    return {"correct": choice == data["answer"], "correct_choice": data["answer"]}
