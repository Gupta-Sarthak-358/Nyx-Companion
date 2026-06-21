import re

SUBJECTS = {
    "verbal": ["reading_comprehension", "grammar", "vocabulary", "sentence_correction"],
    "aptitude": ["quant_arithmetic", "quant_algebra", "logical_reasoning", "data_interpretation"],
    "cs_fundamentals": ["os", "dbms", "cn", "oop"],
    "dsa": [
        "arrays", "linked_list", "stack", "queue", "hashing",
        "binary_search", "sorting", "recursion", "backtracking",
        "trees", "tree", "heap_pq", "graph", "trie", "matrix", "strings",
        "intervals", "bit_manipulation", "math", "greedy", "cyclic_sort",
        "dp", "dynamic_programming",
    ],
    "system_design": ["scalability_basics", "databases_at_scale", "caching", "load_balancing", "case_studies"],
}

# Map PDF filenames → topic for each subject.
# First matching prefix wins.
PDF_TOPIC_MAP: dict[str, list[tuple[str, str]]] = {
    "cs_fundamentals": [
        (r"^Operating_System_Concepts", "os"),
        (r"^Computer_Networking", "cn"),
        (r"^Database_System_Concepts", "dbms"),
        (r"^Object-Oriented_Programming", "oop"),
    ],
    "system_design": [
        (r"^Designing_Data-Intensive", "databases_at_scale"),
        (r"^SystemDesignInterview", "case_studies"),
        (r"^System_Design_Interview", "scalability_basics"),
        (r"^Coding_Interview_Patterns", "case_studies"),
    ],
    "verbal": [
        (r"^Word_Power_Made_Easy", "vocabulary"),
        (r"^GRE_Master_Wordlist", "vocabulary"),
        (r"^Cracking_the_SAT", "reading_comprehension"),
        (r"^english-grammar", "grammar"),
    ],
    "aptitude": [
        (r"^Quantitative_aptitude", "quant_arithmetic"),
        (r"^Data_Interpretation_and_Logical", "logical_reasoning"),
        (r"^Data_Interpretation_Simplified", "data_interpretation"),
        (r"^Verbal_and_Non_Verbal", "quant_arithmetic"),
        (r"^4TH SEM\. BOOKLET", "quant_algebra"),
        (r"^Aptitude_Booklet", "quant_algebra"),
    ],
}


def pdf_filename_to_topic(fname: str, subject: str) -> str | None:
    """Match a PDF filename against known patterns for the given subject."""
    patterns = PDF_TOPIC_MAP.get(subject, [])
    for pat, topic in patterns:
        if re.match(pat, fname):
            return topic
    return None


def is_valid_subject(subject: str) -> bool:
    return subject in SUBJECTS


def is_valid_topic(subject: str, topic: str) -> bool:
    if subject not in SUBJECTS:
        return False
    return topic in SUBJECTS[subject]


def get_topics(subject: str) -> list[str]:
    return SUBJECTS.get(subject, [])
