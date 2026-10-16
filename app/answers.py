"""Versioned answer contract shared by generation, storage and presentation."""
import json

FIELDS = ("number", "question", "clarity", "solution", "answer", "unclear_reason", "recapture_hint")
QUESTION_SCHEMA = {"type": "OBJECT", "properties": {
    **{key: {"type": "STRING"} for key in FIELDS},
    "clarity": {"type": "STRING", "enum": ["clear", "unclear"]},
    "photo_indices": {"type": "ARRAY", "items": {"type": "INTEGER"}},
}, "required": list(FIELDS) + ["photo_indices"]}
ANSWER_SCHEMA = {"type": "OBJECT", "properties": {
    "questions": {"type": "ARRAY", "items": QUESTION_SCHEMA}
}, "required": ["questions"]}


def parse_answer(text, photo_count):
    data = json.loads(text)
    if not isinstance(data, dict) or not isinstance(data.get("questions"), list) or not 1 <= len(data["questions"]) <= 100:
        raise ValueError("解答缺少題目")
    questions = []
    for item in data["questions"]:
        if not isinstance(item, dict) or any(not isinstance(item.get(k), str) for k in FIELDS):
            raise ValueError("解答欄位格式錯誤")
        q = {k: item[k].strip() for k in FIELDS}
        indices = item.get("photo_indices")
        if not isinstance(indices, list) or not indices or any(type(n) is not int or not 1 <= n <= photo_count for n in indices):
            raise ValueError("照片來源錯誤")
        q["photo_indices"] = list(dict.fromkeys(indices))
        q["number"] = q["number"] or "未標示"
        if q["clarity"] == "clear":
            if not all(q[k] for k in ("question", "solution", "answer")):
                raise ValueError("清楚題目缺少解答")
            q["unclear_reason"] = q["recapture_hint"] = ""
        elif q["clarity"] == "unclear":
            # Never publish speculative answers for an unreadable question.
            q["solution"] = q["answer"] = ""
            if not q["unclear_reason"] or not q["recapture_hint"]:
                raise ValueError("缺少補拍說明")
        else:
            raise ValueError("清晰度格式錯誤")
        questions.append(q)
    return {"format": "answer_sheet_v1", "questions": questions}


def answer_text(data):
    blocks = []
    for q in data["questions"]:
        body = f'### {q["number"]}\n題目：{q["question"]}\n'
        if q["clarity"] == "clear":
            body += f'解：{q["solution"]}\n答案：{q["answer"]}'
        else:
            body += f'需補拍：{q["unclear_reason"]}\n{q["recapture_hint"]}'
        blocks.append(body)
    return "\n\n".join(blocks)


def stored_answer(text):
    try:
        data = json.loads(text)
        if isinstance(data, dict) and data.get("format") == "answer_sheet_v1" and isinstance(data.get("questions"), list):
            return data
    except (ValueError, TypeError):
        pass
    return None
