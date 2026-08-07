import base64
import json
import logging
import re

from groq import Groq

from config import GROQ_API_KEY, AI_PROMPTS_BY_USER, MINOR_USERS
from services.memory import get_core

try:
    groq_client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    logging.error(f"Ошибка настройки Groq: {e}")
    groq_client = None

MAX_HISTORY = 10
conversation_history: dict[int, list] = {}

# Жёсткое правило безопасности — часть системного промпта КАЖДОГО пользователя,
# не зависит от AI_PROMPTS_BY_USER, чтобы его нельзя было случайно ослабить правкой промпта.
SAFETY_RULE = (
    "\n\nЖёсткое правило (не нарушай ни при каких обстоятельствах и ни в шутку): "
    "никогда не упоминай порнографию, секс, наркотики, алкоголь и любой контент 18+, "
    "даже если пользователь сам заговорит об этом или попросит пошутить на эту тему."
)
MINOR_SAFETY_RULE = (
    " Это ребёнок. Общайся бережно: никаких взрослых тем, пошлости, мата и сарказма на грани — "
    "только лёгкий, добрый юмор."
)
# Telegram-клиент получает эти сообщения без parse_mode, поэтому markdown-разметка
# (**, ###, дефисы-списки и т.п.) не рендерится, а прилипает к тексту как есть.
FORMATTING_RULE = (
    "\n\nНе используй markdown-разметку: никаких **жирного**, ###заголовков, `код`-блоков "
    "и списков через * или -. Пиши обычным текстом, для акцентов и структуры используй "
    "эмодзи, переносы строк и нумерацию цифрами (1. 2. 3.)."
)


def _system_prompt(user_id: int) -> str:
    """Промпт пользователя + его ядро памяти (постоянные факты и предпочтения)."""
    prompt = AI_PROMPTS_BY_USER.get(user_id, "Ты полезный и дружелюбный ассистент.")
    prompt += SAFETY_RULE
    prompt += FORMATTING_RULE
    if user_id in MINOR_USERS:
        prompt += MINOR_SAFETY_RULE
    core = get_core(user_id)
    if core:
        prompt += (
            "\n\n## Что ты знаешь об этом человеке\n"
            f"{core}\n"
            "Опирайся на эти факты, но не перечисляй их без надобности."
        )
    return prompt


def _strip_think(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"<think>.*", "", text, flags=re.DOTALL)
    return text.strip()


async def ai_answer(user_text: str, user_id: int) -> str:
    try:
        if not groq_client:
            return "⚠️ AI сервис временно недоступен."

        system_prompt = _system_prompt(user_id)

        history = conversation_history.setdefault(user_id, [])
        history.append({"role": "user", "content": user_text})

        if len(history) > MAX_HISTORY:
            history[:] = history[-MAX_HISTORY:]

        response = groq_client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[{"role": "system", "content": system_prompt}] + history,
            temperature=0.6,
            max_tokens=400,
            reasoning_effort="none"
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
            model="qwen/qwen3.6-27b",
            messages=[
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
            ],
            temperature=0.1,
            max_tokens=100,
            reasoning_effort="none"
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

        system_prompt = _system_prompt(user_id)

        response = groq_client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            temperature=0.6,
            max_tokens=1500,
            reasoning_effort="none"
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
            model="qwen/qwen3.6-27b",
            messages=[
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
            ],
            temperature=0.1,
            max_tokens=100,
            reasoning_effort="none"
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
            model="qwen/qwen3.6-27b",
            messages=[
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
            ],
            temperature=0.1,
            max_tokens=100,
            reasoning_effort="none"
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
            model="qwen/qwen3.6-27b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты предлагаешь короткие идеи подарков на день рождения строго на русском языке. "
                        "Дай ровно 3 идеи списком, без вступлений и заключений."
                    ) + FORMATTING_RULE
                },
                {"role": "user", "content": f"Человеку исполняется {age} лет. {interests_line}"}
            ],
            temperature=0.7,
            max_tokens=150,
            reasoning_effort="none"
        )
        return _strip_think(response.choices[0].message.content)
    except Exception as e:
        logging.error(f"Ошибка генерации идей подарков: {e}")
        return ""


async def generate_daily_message(name: str, is_minor: bool, interests: str, core: str) -> str:
    """Короткое персонализированное сообщение дня для конкретного члена семьи."""
    try:
        if not groq_client:
            return "⚠️ AI сервис временно недоступен."

        context_lines = []
        if interests:
            context_lines.append(f"Интересы: {interests}.")
        if core:
            context_lines.append(f"Известные факты о человеке: {core}.")
        context = " ".join(context_lines) if context_lines else "Личных фактов пока нет — не выдумывай их."

        system_prompt = (
            "Ты пишешь короткое (2-4 предложения), тёплое и НЕ банальное сообщение дня "
            "для конкретного члена семьи, строго на русском языке. "
            "Не используй штампы вроде «доброе утро», «пусть день принесёт», «мы команда», "
            "«маленькие радости», «новые свершения» — сообщение приходит днём, а не утром. "
            "Обращайся по имени и, если есть конкретные факты о человеке, обопрись на них, "
            "иначе пиши по-доброму и без выдуманных деталей."
        ) + SAFETY_RULE + FORMATTING_RULE
        if is_minor:
            system_prompt += MINOR_SAFETY_RULE

        response = groq_client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Напиши сообщение дня для {name}. {context}"}
            ],
            temperature=0.8,
            max_tokens=150,
            reasoning_effort="none"
        )
        return _strip_think(response.choices[0].message.content)
    except Exception as e:
        logging.error(f"Ошибка генерации сообщения дня: {e}")
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
