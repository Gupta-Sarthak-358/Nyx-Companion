"""Generate sample MCQ questions for manual quality review.

Usage:
    PYTHONPATH=. python3 scripts/dump_mcq_questions.py [--count N] [--subject SUBJECT]

Generates N questions (default 5) per subject (or specified subject) and writes
to output/mcq_samples.json.

Requires: llama-server running, PDFs ingested per subject.
"""

import asyncio
import json
import os
import sys
import argparse

_script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_script_dir))  # adds backend/ to path

from mcq.mcq_prompt import generate_mcq
from mcq.taxonomy import SUBJECTS


async def main():
    parser = argparse.ArgumentParser(description="Generate MCQ samples for manual review")
    parser.add_argument("--count", type=int, default=5, help="Total questions per subject (default: 5)")
    parser.add_argument("--subject", type=str, default=None, help="Specific subject (default: all)")
    parser.add_argument("--topic", type=str, default=None, help="Specific topic (optional)")
    parser.add_argument("--output", type=str, default="output/mcq_samples.json", help="Output file")
    args = parser.parse_args()

    subjects = [args.subject] if args.subject else list(SUBJECTS.keys())
    results = []

    for subj in subjects:
        if args.topic:
            topic_diff_pairs = [(args.topic, d) for d in [1, 3, 5]]
        elif args.subject:
            import random
            topics = SUBJECTS.get(subj, [])
            random.shuffle(topics)
            topic_diff_pairs = []
            for t in topics[:5]:
                for d in [1, 3, 5]:
                    topic_diff_pairs.append((t, d))
            topic_diff_pairs = topic_diff_pairs[:args.count]
        else:
            topic_diff_pairs = [(None, d) for d in [1, 3, 5]]

        for topic, diff in topic_diff_pairs:
            q = await generate_mcq(subj, topic=topic, difficulty=diff)
            if q:
                results.append({
                    "subject": subj,
                    "topic": q.get("topic"),
                    "difficulty": diff,
                    "question": q["question"],
                    "options": q["options"],
                    "correct_index": q["correct_index"],
                    "explanation": q["explanation"],
                })

    os.makedirs("output", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Generated {len(results)} questions → {args.output}")
    for r in results:
        print(f"  [{r['subject']}] Lv.{r['difficulty']}: {r['question'][:60]}...")


if __name__ == "__main__":
    asyncio.run(main())
