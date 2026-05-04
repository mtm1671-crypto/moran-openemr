from app.document_models import ExtractedFact, W2FactStatus


def reviewable_facts(facts: list[ExtractedFact]) -> list[ExtractedFact]:
    return [fact for fact in facts if fact.status == W2FactStatus.review_required]


def approved_facts(facts: list[ExtractedFact]) -> list[ExtractedFact]:
    return [fact for fact in facts if fact.status == W2FactStatus.approved]


def written_facts(facts: list[ExtractedFact]) -> list[ExtractedFact]:
    return [fact for fact in facts if fact.status == W2FactStatus.written]

