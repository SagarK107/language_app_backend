from . import models

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
        "sub": item.transliteration if side == "text" else "",
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
