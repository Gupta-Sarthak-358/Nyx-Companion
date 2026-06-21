import json
import random
import re
import tempfile
import base64
import asyncio
from asyncio import Semaphore
from contextlib import suppress

from fastapi import WebSocket

from llm_client import ask_llm, ask_llm_stream
from nyx_personality import clean_response, trim_turns, choose_tone
from mode_utils import (
    parse_evaluation,
    rebuild_history,
    analyze_feedback,
    is_garbage_transcription,
    get_difficulty_label,
)
from tts import generate_tts
from log_utils import logger
from rag.eval_logger import log_rag_turn
import prompt_loader


async def init_mode(data, state, system_template, rag_available):
    mode = data.get("mode", "STRUCTURED").upper()
    custom_desc = data.get("description", "").strip()
    logger.info("Starting session in %s mode", mode)

    state["current_mode"] = mode
    state["history_turns"] = []
    state["session_evals"] = []
    state["session_acoustic_hits"] = {"filler_total": 0, "turn_count": 0, "wpm_values": []}
    state["rag_context_log"] = []
    state["conversation_history"] = ""
    state["is_scenario_setup_needed"] = False
    state["_llm_semaphore"] = Semaphore(1)
    state["_last_msg_time"] = 0.0

    tc_block = f"\n\nTOPIC CONSTRAINT: Focus questions on {custom_desc}. Do not ask about unrelated topics." if custom_desc else ""

    if mode == "STRUCTURED":
        state["user_role"], state["ai_role"] = "Candidate", "Interviewer"
        opening = "Hello! I'm your AI interviewer. Let's begin. Tell me about yourself."
        state["system_prompt"] = system_template.replace("{MODE}", mode).replace("{TOPIC_CONSTRAINT}", tc_block)
    elif mode == "TOPIC":
        state["user_role"], state["ai_role"] = "Speaker", "Moderator"
        topic = random.choice(["Future of AI", "Remote Work", "Cybersecurity", "Ethics in Tech"])
        opening = f"Welcome. Today I'd like you to speak about: {topic}."
        state["system_prompt"] = system_template.replace("{MODE}", mode).replace("{TOPIC_CONSTRAINT}", "")
    elif mode == "TUTOR":
        state["user_role"], state["ai_role"] = "Student", "Tutor"
        if not rag_available:
            opening = "RAG module is not available. Check that rag/ is installed."
            state["system_prompt"] = "You are a helpful assistant."
        else:
            opening = "Hello! I'm your personal tutor. Ask me anything from your knowledge base."
            state["system_prompt"] = prompt_loader.get("tutor", "system")
            if custom_desc:
                state["system_prompt"] += f"\n\nTOPIC CONSTRAINT: Focus on {custom_desc}."
    elif mode == "CONVERSATION":
        if custom_desc:
            await state["ws"].send_json({"type": "user_speech", "text": f"[Scenario: {custom_desc}]", "feedback": None})
            parse_prompt = f"Analyze Scenario: '{custom_desc}'. Define AI role, User role, and a natural OPENING LINE for the AI. Return JSON: {{\"ai_role\": \"...\", \"user_role\": \"...\", \"opening\": \"...\", \"context\": \"...\"}}"
            try:
                res = await ask_llm(parse_prompt, stop_tokens=["}"], task_name="Director Setup")
                setup = json.loads(res + ("}" if not res.endswith("}") else ""))
                state["ai_role"], state["user_role"] = setup["ai_role"], setup["user_role"]
                opening = setup["opening"]
                state["system_prompt"] = f"Roleplay: You are {state['ai_role']}. User is {state['user_role']}. Context: {setup['context']}"
            except (json.JSONDecodeError, KeyError):
                logger.exception("Director setup failed")
                state["ai_role"], state["user_role"] = "AI", "User"
                opening = "Hello, I'm ready for our conversation."
                state["system_prompt"] = f"Roleplay as a companion. Context: {custom_desc}"
        else:
            state["ai_role"], state["user_role"] = "AI", "User"
            opening = "What scenario would you like to simulate today?"
            state["system_prompt"] = "You are a roleplay director. Ask the user for a scenario."
            state["is_scenario_setup_needed"] = True
    else:
        state["user_role"], state["ai_role"] = "User", "Assistant"
        opening = "Hello. How can I help?"
        state["system_prompt"] = system_template.replace("{MODE}", mode)

    state["history_turns"].append(f"{state['ai_role']}: {opening}")
    state["conversation_history"] = rebuild_history(state["current_mode"], state["history_turns"], state["system_prompt"])
    await state["ws"].send_json({"type": "ai_response", "text": opening})
    await generate_tts(opening, state["ws"])


async def handle_interview_chat(state):
    ws = state["ws"]
    user_text = state["data"]["text"].strip()
    if not user_text:
        return

    await ws.send_json({"type": "user_speech", "text": user_text, "feedback": None})
    await ws.send_json({"type": "status", "message": "Thinking..."})

    cm = state["current_mode"]
    if cm == "TUTOR" and state.get("rag_available"):
        from rag.integration import build_rag_prompt
        rag_prompt, rag_results = build_rag_prompt(
            user_text, top_k=5, conversation_history=state.get("rag_context_log", []),
        )
        if rag_results:
            state["system_prompt"] = rag_prompt
            ai_prompt = f"{state['user_role']}: {user_text}\n{state['ai_role']}:"
            state.setdefault("rag_context_log", []).append(
                {"q": user_text, "sources": list(set(m.get("source", "?") for _, m, _ in rag_results))}
            )
        else:
            ai_prompt = f"{state['conversation_history']}\n{state['user_role']}: {user_text}\n{state['ai_role']}:"
    else:
        ai_prompt = f"{state['conversation_history']}\n{state['user_role']}: {user_text}\n{state['ai_role']}:"

    async with state["_llm_semaphore"]:
        full_res = ""
        from metrics import Timer
        with Timer("llm_generate"):
            async for token in ask_llm_stream(ai_prompt):
                full_res += token
                await ws.send_json({"type": "ai_token", "token": token})

    full_res = clean_response(full_res, state["user_role"], state["ai_role"])
    if not full_res:
        await ws.send_json({"type": "status", "message": "Sorry, I couldn't generate a response. Please try again."})
        return

    state["history_turns"].extend([f"{state['user_role']}: {user_text}", f"{state['ai_role']}: {full_res}"])
    state["history_turns"] = trim_turns(state["history_turns"])
    state["conversation_history"] = rebuild_history(cm, state["history_turns"], state["system_prompt"])
    if cm == "TUTOR" and state.get("rag_context_log"):
        log_rag_turn(user_text, rag_results, full_res)
    await ws.send_json({"type": "ai_response", "text": full_res})
    await generate_tts(full_res, ws)


async def handle_interview_audio(state):
    ws = state["ws"]
    data = state["data"]
    whisper_model = state["whisper_model"]

    audio_bytes = base64.b64decode(data.get("data"))
    path = ""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
        f.write(audio_bytes)
        path = f.name

    await ws.send_json({"type": "status", "message": "Transcribing..."})
    try:
        segments, info = whisper_model.transcribe(path)
        segments = list(segments)
        user_text = " ".join(s.text for s in segments).strip()
    finally:
        with suppress(OSError):
            import os
            os.unlink(path)

    if is_garbage_transcription(user_text):
        msg = "I didn't catch that. Could you repeat?"
        await ws.send_json({"type": "ai_response", "text": msg})
        await generate_tts(msg, ws)
        return

    acoustic_feedback = analyze_feedback(
        user_text,
        info.duration,
        sum(s.avg_logprob for s in segments) / len(segments) if segments else -1,
    )
    await ws.send_json({"type": "status", "message": "Thinking..."})

    cm = state["current_mode"]
    if cm == "CONVERSATION" and state.get("is_scenario_setup_needed"):
        res = await ask_llm(
            f"The user wants this scenario: '{user_text}'. Return JSON: {{\"ai_role\": \"...\", \"user_role\": \"...\", \"context\": \"...\", \"response\": \"...\"}}"
        )
        try:
            setup = json.loads(res + ("}" if not res.endswith("}") else ""))
            state["ai_role"], state["user_role"] = setup["ai_role"], setup["user_role"]
            ai_response = setup["response"]
            state["system_prompt"] = f"Roleplay: You are {state['ai_role']}. User is {state['user_role']}. Context: {setup['context']}"
            state["history_turns"] = [f"{state['user_role']}: {user_text}", f"{state['ai_role']}: {ai_response}"]
            state["is_scenario_setup_needed"] = False
            eval_data = {"relevance": 100, "depth": 100, "clarity": 100, "structure": 100, "confidence": 100, "suggestion": "Let's go!"}
        except (json.JSONDecodeError, KeyError):
            logger.exception("Scenario setup from audio failed")
            state["ai_role"], state["user_role"] = "Friend", "Friend"
            ai_response = "Got it."
            state["system_prompt"] = "Roleplay as friend."
            state["history_turns"] = [f"{state['user_role']}: {user_text}", f"{state['ai_role']}: {ai_response}"]
            state["is_scenario_setup_needed"] = False
            eval_data = {"relevance": 100, "depth": 100, "clarity": 100, "structure": 100, "confidence": 100, "suggestion": "Ready."}

    if cm == "TUTOR" and state.get("rag_available"):
        from rag.integration import build_rag_prompt
        rag_prompt, rag_results = build_rag_prompt(
            user_text, top_k=5, conversation_history=state.get("rag_context_log", []),
        )
        if rag_results:
            state["system_prompt"] = rag_prompt
            ai_prompt = f"{state['user_role']}: {user_text}\n{state['ai_role']}:"
            state.setdefault("rag_context_log", []).append(
                {"q": user_text, "sources": list(set(m.get("source", "?") for _, m, _ in rag_results))}
            )
        else:
            ai_prompt = f"{state['conversation_history']}\n{state['user_role']}: {user_text}\n{state['ai_role']}:"
    else:
        ai_prompt = f"{state['conversation_history']}\n{state['user_role']}: {user_text}\n{state['ai_role']}:"

    async with state["_llm_semaphore"]:
        from metrics import Timer
        with Timer("llm_generate"):
            raw_res = await ask_llm(ai_prompt)

    if cm == "TUTOR":
        full_res = clean_response(raw_res, state["user_role"], state["ai_role"])
        if not full_res:
            await ws.send_json({"type": "status", "message": "Sorry, I couldn't generate a response. Please try again."})
            return
        state["history_turns"].extend([f"{state['user_role']}: {user_text}", f"{state['ai_role']}: {full_res}"])
        if len(state["history_turns"]) > 20:
            state["history_turns"] = state["history_turns"][-20:]
        state["conversation_history"] = rebuild_history(cm, state["history_turns"], state["system_prompt"])
        log_rag_turn(user_text, rag_results, full_res)
        await ws.send_json({"type": "ai_response", "text": full_res})
        await generate_tts(full_res, ws)
        return

    if cm == "CONVERSATION" and state.get("is_scenario_setup_needed") is False:
        pass  # scenario was set up above

    if not raw_res:
        await ws.send_json({"type": "status", "message": "Sorry, I couldn't generate a response. Please try again."})
        return

    eval_data, full_res = parse_evaluation(raw_res)
    if eval_data is None:
        eval_data = {"relevance": 70, "depth": 50, "clarity": 70, "structure": 70, "confidence": 70, "suggestion": "Keep focusing on details."}

    state.setdefault("session_evals", []).append(eval_data)
    state["session_acoustic_hits"]["filler_total"] += acoustic_feedback["filler_words_count"]
    state["session_acoustic_hits"]["turn_count"] += 1
    state["session_acoustic_hits"]["wpm_values"].append(acoustic_feedback["wpm"])

    depth = eval_data["depth"]
    difficulty_hint = get_difficulty_label(depth, len(state["history_turns"]))
    if difficulty_hint:
        full_res += difficulty_hint

    full_res = clean_response(full_res, state["user_role"], state["ai_role"])
    state["history_turns"].extend([f"{state['user_role']}: {user_text}", f"{state['ai_role']}: {full_res}"])
    if len(state["history_turns"]) > 20:
        state["history_turns"] = state["history_turns"][-20:]

    state["conversation_history"] = rebuild_history(cm, state["history_turns"], state["system_prompt"])
    combined_feedback = acoustic_feedback
    combined_feedback.update({"relevance": eval_data["relevance"], "depth": eval_data["depth"]})
    combined_feedback["suggestions"].append(eval_data["suggestion"])
    await ws.send_json({"type": "user_speech", "text": user_text, "feedback": combined_feedback})
    await ws.send_json({"type": "ai_response", "text": full_res})
    await generate_tts(full_res, ws)


async def handle_retry(state):
    ws = state["ws"]
    prompt = f"{state['conversation_history']}\n({state['ai_role']} repeats or rephrases the last question.)\n{state['ai_role']}:"
    async with state["_llm_semaphore"]:
        res = await ask_llm(prompt)
    if not res:
        await ws.send_json({"type": "status", "message": "Sorry, I couldn't retry. Please try again."})
        return
    res = re.sub(rf"^({state['ai_role']}|AI):", "", res, flags=re.I).strip()
    state["history_turns"].append(f"{state['ai_role']} (Retry): {res}")
    await ws.send_json({"type": "ai_response", "text": res})
    await generate_tts(res, ws)


async def handle_nudge(state):
    ws = state["ws"]
    prompt = f"{state['conversation_history']}\n({state['ai_role']} gently prompts {state['user_role']}.)\n{state['ai_role']}:"
    async with state["_llm_semaphore"]:
        res = await ask_llm(prompt)
    if not res:
        await ws.send_json({"type": "status", "message": "Sorry, I couldn't nudge. Please try again."})
        return
    res = re.sub(rf"^({state['ai_role']}|AI):", "", res, flags=re.I).strip()
    state["history_turns"].append(f"{state['ai_role']} (Nudge): {res}")
    await ws.send_json({"type": "ai_response", "text": res})
    await generate_tts(res, ws)


async def handle_end_interview(state):
    ws = state["ws"]
    session_evals = state.get("session_evals", [])
    if not session_evals:
        await ws.send_json({"type": "report", "data": None})
        return

    avg = {k: sum(d[k] for d in session_evals) / len(session_evals) for k in ("clarity", "structure", "confidence", "relevance", "depth")}
    strengths = sorted(avg, key=avg.get, reverse=True)[:2]
    weaknesses = sorted(avg, key=avg.get)[:2]

    ah = state.get("session_acoustic_hits", {})
    wpm_vals = ah.get("wpm_values", [])
    avg_wpm = sum(wpm_vals) / len(wpm_vals) if wpm_vals else 0

    report = {
        "total_questions": len(session_evals),
        "average": avg,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "avg_wpm": round(avg_wpm),
        "total_filler_words": ah.get("filler_total", 0),
        "mode": state.get("current_mode", "UNKNOWN"),
    }
    await ws.send_json({"type": "report", "data": report})


import uuid
from mcq.adaptive import AdaptiveDifficulty
from mcq.mcq_prompt import generate_mcq


async def handle_mcq_message(state):
    ws = state["ws"]
    data = state["data"]
    msg_type = data.get("type")

    if msg_type == "mcq_start":
        subject = data.get("subject")
        topic = data.get("topic")
        if not subject:
            await ws.send_json({"type": "mcq_error", "message": "No subject specified"})
            return

        state["mcq_subject"] = subject
        state["mcq_topic"] = topic
        if "mcq_difficulty" not in state:
            state["mcq_difficulty"] = AdaptiveDifficulty()
        if "mcq_stats" not in state:
            state["mcq_stats"] = {"asked": 0, "correct": 0}
        if "mcq_current_question" in state:
            del state["mcq_current_question"]

        difficulty = state["mcq_difficulty"].get_difficulty(subject)
        question = await generate_mcq(subject, topic=topic, difficulty=difficulty)
        if question is None:
            await ws.send_json({
                "type": "mcq_error",
                "message": f"No material available for '{subject}'. Drop PDFs into knowledge/books/{subject}/ and re-ingest.",
            })
            return

        qid = str(uuid.uuid4())
        state["mcq_current_question"] = {**question, "id": qid}
        await ws.send_json({
            "type": "mcq_question",
            "id": qid,
            "subject": subject,
            "topic": topic,
            "difficulty": difficulty,
            "question": question["question"],
            "options": question["options"],
        })

    elif msg_type == "mcq_answer":
        qid = data.get("question_id")
        selected = data.get("selected_index")
        current = state.get("mcq_current_question")
        if not current or current.get("id") != qid:
            await ws.send_json({"type": "mcq_error", "message": "Question expired or not found"})
            return

        subject = state.get("mcq_subject")
        correct = selected == current["correct_index"]
        state["mcq_stats"]["asked"] += 1
        if correct:
            state["mcq_stats"]["correct"] += 1

        updated = state["mcq_difficulty"].record_answer(subject, correct)
        difficulty = updated["current_difficulty"]

        await ws.send_json({
            "type": "mcq_result",
            "correct": correct,
            "correct_index": current["correct_index"],
            "explanation": current.get("explanation", ""),
            "new_difficulty": difficulty,
            "streak_correct": updated["streak_correct"],
            "streak_wrong": updated["streak_wrong"],
            "stats": dict(state["mcq_stats"]),
        })

    elif msg_type == "mcq_next":
        subject = state.get("mcq_subject")
        topic = state.get("mcq_topic")
        if not subject:
            await ws.send_json({"type": "mcq_error", "message": "No active subject"})
            return

        difficulty = state["mcq_difficulty"].get_difficulty(subject)
        question = await generate_mcq(subject, topic=topic, difficulty=difficulty)
        if question is None:
            await ws.send_json({
                "type": "mcq_error",
                "message": f"Could not generate more questions for '{subject}'.",
            })
            return

        qid = str(uuid.uuid4())
        state["mcq_current_question"] = {**question, "id": qid}
        await ws.send_json({
            "type": "mcq_question",
            "id": qid,
            "subject": subject,
            "topic": topic,
            "difficulty": difficulty,
            "question": question["question"],
            "options": question["options"],
        })

    elif msg_type == "mcq_end":
        stats = state.get("mcq_stats", {"asked": 0, "correct": 0})
        subject = state.get("mcq_subject", "unknown")
        diff = state["mcq_difficulty"].get_difficulty(subject) if "mcq_difficulty" in state else 3
        await ws.send_json({
            "type": "mcq_summary",
            "subject": subject,
            "topic": state.get("mcq_topic"),
            "difficulty": diff,
            "stats": stats,
        })
        if "mcq_current_question" in state:
            del state["mcq_current_question"]
