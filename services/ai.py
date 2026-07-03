import base64
import json
import logging
import re

from groq import Groq

from config import GROQ_API_KEY, AI_PROMPTS_BY_USER

try:
    groq_client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    logging.error(f"Ошибка настройки Groq: {e}")
    groq_client = None

MAX_HISTORY = 10
conversation_history: dict[int, list] = {}


def _strip_think(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"<think>.*", "", text, flags=re.DOTALL)
    return text.strip()


def _no_think(messages: list) -> list:
    """Отключает thinking-mode у Qwen3 через токен /no_think в последнем user-сообщении."""
    result = []
    for msg in reversed(messages):
        if msg["role"] == "user" and not result:
            content = msg["content"]
            if isinstance(content, str):
                result.insert(0, {**msg, "content": f"/no_think\n{content}"})
            else:
                result.insert(0, msg)
        else:
            result.insert(0, msg)
    return result


async def ai_answer(user_text: str, user_id: int) -> str:
    try:
        if not groq_client:
            return "⚠️ AI сервис временно недоступен."

        system_prompt = AI_PROMPTS_BY_USER.get(
            user_id,
            "Ты полезный и дружелюбный ассистент."
        )

        history = conversation_history.setdefault(user_id, [])
        history.append({"role": "user", "content": user_text})

        if len(history) > MAX_HISTORY:
            history[:] = history[-MAX_HISTORY:]

        response = groq_client.chat.completions.create(
            model="qwen/qwen3-32b",
            messages=_no_think([{"role": "system", "content": system_prompt}] + history),
            temperature=0.6,
            max_tokens=400
        )

        assistant_reply = _strip_think(response.choices[0].message.content)
        history.append({"role": "assistant", "content": assistant_reply})

        if len(history) > MAX_HISTORY:
            history[:] = history[-MAX_HISTORY:]

        return assistant_reply

    except Exception as e:
        logging.error(f"Ошибка AI (Groq): {e}")
        return "⚠️ Произошла ошибка при обращении к AI."


def reset_history(user_id: int):
    conversation_history.pop(user_id, None)


async def parse_reminder_request(text: str, now_str: str) -> dict | None:
    try:
        if not groq_client:
            return None
        response = groq_client.chat.completions.create(
            model="qwen/qwen3-32b",
            messages=_no_think([
                {
                    "role": "system",
                    "content": (
                        f"Сейчас: {now_str} (московское время).\n"
                        "Из текста пользователя извлеки время напоминания и его текст.\n"
                        "Верни ТОЛЬКО JSON без лишнего текста:\n"
                        '{"datetime": "YYYY-MM-DD HH:MM", "text": "текст напоминания"}\n'
                        'Если время нельзя определить, верни: {"error": "не могу определить время"}'
                    )
                },
                {"role": "user", "content": text}
            ]),
            temperature=0.1,
            max_tokens=100
        )
        content = _strip_think(response.choices[0].message.content)
        match = re.search(r"```(?:json)?\s*(.*?)```", content, re.DOTALL)
        if match:
            content = match.group(1).strip()
        return json.loads(content)
    except Exception as e:
        logging.error(f"Ошибка парсинга напоминания: {e}")
        return None


async def analyze_image(image_path: str, prompt: str, user_id: int) -> str:
    try:
        if not groq_client:
            return "⚠️ AI сервис временно недоступен."

        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        system_prompt = AI_PROMPTS_BY_USER.get(user_id, "Ты полезный и дружелюбный ассистент.")

        response = groq_client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                        {"type": "text", "text": f"/no_think\n{prompt}"},
                    ],
                }
            ],
            temperature=0.6,
            max_tokens=1500
        )

        reply = _strip_think(response.choices[0].message.content)

        history = conversation_history.setdefault(user_id, [])
        history.append({"role": "user", "content": f"[фото] {prompt}"})
        history.append({"role": "assistant", "content": reply})
        if len(history) > MAX_HISTORY:
            history[:] = history[-MAX_HISTORY:]

        return reply

    except Exception as e:
        logging.error(f"Ошибка анализа изображения ({type(e).__name__}): {e}")
        return f"⚠️ Не удалось проанализировать фото: {e}"


async def parse_training_delete(text: str, trainings: dict) -> dict | None:
    try:
        if not groq_client:
            return None
        trainings_str = json.dumps(trainings, ensure_ascii=False)
        response = groq_client.chat.completions.create(
            model="qwen/qwen3-32b",
            messages=_no_think([
                {
                    "role": "system",
                    "content": (
                        f"Текущие тренировки: {trainings_str}\n"
                        "Из запроса пользователя определи, какую тренировку нужно удалить.\n"
                        "Верни ТОЛЬКО JSON без лишнего текста:\n"
                        '{"child": "имя ребёнка", "day": "день недели", "time": "время или его часть"}\n'
                        'Если не можешь определить, верни: {"error": "не могу определить"}'
                    )
                },
                {"role": "user", "content": text}
            ]),
            temperature=0.1,
            max_tokens=100
        )
        content = _strip_think(response.choices[0].message.content)
        match = re.search(r"```(?:json)?\s*(.*?)```", content, re.DOTALL)
        if match:
            content = match.group(1).strip()
        return json.loads(content)
    except Exception as e:
        logging.error(f"Ошибка парсинга удаления тренировки: {e}")
        return None


async def parse_wishlist_add(text: str) -> dict | None:
    try:
        if not groq_client:
            return None
        response = groq_client.chat.completions.create(
            model="qwen/qwen3-32b",
            messages=_no_think([
                {
                    "role": "system",
                    "content": (
                        "Из фразы пользователя извлеки, что он хочет получить в подарок.\n"
                        "Верни ТОЛЬКО JSON без лишнего текста:\n"
                        '{"item": "краткое описание желаемого подарка"}\n'
                        'Если не можешь определить, верни: {"error": "не могу определить"}'
                    )
                },
                {"role": "user", "content": text}
            ]),
            temperature=0.1,
            max_tokens=100
        )
        content = _strip_think(response.choices[0].message.content)
        match = re.search(r"```(?:json)?\s*(.*?)```", content, re.DOTALL)
        if match:
            content = match.group(1).strip()
        return json.loads(content)
    except Exception as e:
        logging.error(f"Ошибка парсинга списка желаний: {e}")
        return None


async def generate_gift_ideas(name: str, age: int, interests: str) -> str:
    try:
        if not groq_client:
            return ""
        interests_line = (
            f"Интересы: {interests}."
            if interests
            else "Интересы неизвестны — предложи универсальные варианты для этого возраста."
        )
        response = groq_client.chat.completions.create(
            model="qwen/qwen3-32b",
            messages=_no_think([
                {
                    "role": "system",
                    "content": (
                        "Ты предлагаешь короткие идеи подарков на день рождения строго на русском языке. "
                        "Дай ровно 3 идеи списком, без вступлений и заключений."
                    )
                },
                {"role": "user", "content": f"Человеку исполняется {age} лет. {interests_line}"}
            ]),
            temperature=0.7,
            max_tokens=150
        )
        return _strip_think(response.choices[0].message.content)
    except Exception as e:
        logging.error(f"Ошибка генерации идей подарков: {e}")
        return ""


async def transcribe_voice(file_path: str) -> str | None:
    try:
        if not groq_client:
            return None
        with open(file_path, "rb") as f:
            transcription = groq_client.audio.transcriptions.create(
                file=(file_path, f.read()),
                model="whisper-large-v3-turbo",
                language="ru"
            )
        return transcription.text
    except Exception as e:
        logging.error(f"Ошибка транскрипции голоса: {e}")
        return None
