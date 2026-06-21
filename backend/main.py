import asyncio

from speech_to_text import record_audio, transcribe_audio
from text_to_speech import speak
from interviewer import ask_llm

DURATION = 15

with open("prompt.txt") as f:
    system_prompt = f.read()

conversation = system_prompt + "\nInterviewer:"

print("AI Interviewer started. Press Ctrl+C to stop.\n")


async def main():
    global conversation
    while True:
        audio_file = record_audio(duration=DURATION)
        user_text = transcribe_audio(audio_file)

        if not user_text:
            print("Could not understand. Try again.")
            continue

        print(f"\nYou: {user_text}\n")

        conversation += f"\nCandidate: {user_text}\nInterviewer:"

        response = await ask_llm(conversation)

        conversation += response + "\nInterviewer:"

        speak(response)


if __name__ == "__main__":
    asyncio.run(main())