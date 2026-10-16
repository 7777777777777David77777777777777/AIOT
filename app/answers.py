"""Versioned answer contract shared by generation, storage and presentation."""
import json
from app.answer_checks import check_question

FIELDS = ("number", "question", "clarity", "solution", "answer", "unclear_reason", "recapture_hint")
QUESTION_SCHEMA = {"type": "OBJECT", "properties": {
    **{key: {"type": "STRING"} for key in FIELDS},
    "clarity": {"type": "STRING", "enum": ["clear", "unclear"]},
    "photo_indices": {"type": "ARRAY", "items": {"type": "INTEGER"}},
    "confidence": {"type": "INTEGER", "minimum": 0, "maximum": 100, "description": "模型對本題答案的自評信心百分比，不是驗證結果"},
}, "required": list(FIELDS) + ["photo_indices", "confidence"]}
ANSWER_SCHEMA = {"type": "OBJECT", "properties": {
    "questions": {"type": "ARRAY", "items": QUESTION_SCHEMA},
    "chat_metadata": {"type": "OBJECT", "properties": {"exam_title": {"type": "STRING"}, "subject": {"type": "STRING"}}, "required": ["exam_title", "subject"]}
}, "required": ["questions", "chat_metadata"]}


def parse_answer(text, photo_count):
    data = json.loads(text)
    if not isinstance(data, dict) or not isinstance(data.get("questions"), list) or not 1 <= len(data["questions"]) <= 100:
        raise ValueError("解答缺少題目")
    questions = []
    for item in data["questions"]:
        if not isinstance(item, dict) or any(not isinstance(item.get(k), str) for k in FIELDS):
            raise ValueError("解答欄位格式錯誤")
        q = {k: item[k].strip() for k in FIELDS}
        confidence = item.get('confidence')
        if confidence is not None and (type(confidence) is not int or not 0 <= confidence <= 100):
            raise ValueError('模型信心必須是 0 至 100 的整數')
        q['confidence'] = confidence
        indices = item.get("photo_indices")
        if not isinstance(indices, list) or not indices or any(type(n) is not int or not 1 <= n <= photo_count for n in indices):
            raise ValueError("照片來源錯誤")
        q["photo_indices"] = list(dict.fromkeys(indices))
        q["number"] = q["number"] or "未標示"
        if q["clarity"] == "clear":
            if not q["question"]:
                raise ValueError("清楚題目缺少解答")
            q["unclear_reason"] = q["recapture_hint"] = ""
        elif q["clarity"] == "unclear":
            # Never publish speculative answers for an unreadable question.
            q["solution"] = q["answer"] = ""
            if not q["unclear_reason"] or not q["recapture_hint"]:
                raise ValueError("缺少補拍說明")
        else:
            raise ValueError("清晰度格式錯誤")
        questions.append(check_question(q))
    meta = data.get('chat_metadata') or {}
    if not isinstance(meta, dict):
        meta = {}
    meta = {key: ' '.join(meta.get(key, '').split())[:100] if isinstance(meta.get(key), str) else '' for key in ('exam_title', 'subject')}
    return {"format": "answer_sheet_v1", "questions": questions, "chat_metadata": meta}


def answer_text(data):
    blocks = []
    for q in data["questions"]:
        body = f'### {q["number"]}\n題目：{q["question"]}\n'
        if q["clarity"] == "clear":
            body += f'解：{q["solution"]}\n'
            if q.get('answer_status') == 'needs_review':
                body += '答案：待確認\n' + q.get('review_note', '')
            else:
                body += f'答案：{q["answer"]}\n（尚未獨立查證）'
        else:
            body += f'答案：無法作答：照片不清楚\n需補拍：{q["unclear_reason"]}\n{q["recapture_hint"]}'
        blocks.append(body)
    return "\n\n".join(blocks)


def stored_answer(text):
    try:
        data = json.loads(text)
        if isinstance(data, dict) and data.get("format") == "answer_sheet_v1" and isinstance(data.get("questions"), list):
            data['questions'] = [check_question(q) for q in data['questions']]
            return data
    except (ValueError, TypeError):
        pass
    return None
