"""Conservative output checks, not a claim of factual verification."""
import re


def check_question(q):
    q = dict(q)
    confidence = q.get('confidence')
    q['confidence'] = confidence if type(confidence) is int and 0 <= confidence <= 100 else None
    issues = []
    solution = q.get('solution', '')
    answer = q.get('answer', '').strip()
    previously_deferred = q.get('answer_status') == 'needs_review'
    q['answer_status'] = 'unverified'
    if q.get('clarity') == 'unclear':
        q['answer_status'] = 'needs_review'
    if q.get('clarity') == 'clear' and not solution.strip():
        issues.append('沒有解題說明，答案尚待確認。')
    if re.search(r'字形模糊|無法辨識|看不清|選項殘缺|缺少關鍵條件', solution):
        issues.append('解說提到辨識或條件不足，與確定作答不一致。')
    if re.search(r'暫以|依常見答案|依標準答案|通常此題標準答案|此處依常見|或含標點|或特定段落|經查對應字數', solution):
        issues.append('解說含猜測或未提供可核對依據，不能據此確定選項。')
    if q.get('clarity') == 'clear' and (answer in {'略', '不詳', '不知道', '待確認', '無法判斷'} or (not answer and not previously_deferred)):
        issues.append('沒有完整答案。')
    if re.search(r'☠|\[\s*[…\.]\s*\]', solution):
        issues.append('解說含異常符號或缺漏文字。')
    count_task = bool(re.search(r'幾(?:個)?字|字數|多少字', q.get('question', '')))
    if count_task:
        # A correct count of an invented passage still does not answer the question.
        issues.append('原文與默寫範圍尚未獨立確認，暫不確定選項。')
        counts = []
        for quote in re.findall(r'「([^「」]+)」', solution):
            if re.search(r'[…\.]{2,}|…', quote):
                continue
            count = len(re.findall(r'[\u3400-\u4dbf\u4e00-\u9fff\U00020000-\U0002ffff]', quote))
            if count:
                counts.append({'text': quote, 'count': count})
        q['count_checks'] = counts
    if issues or q.get('clarity') == 'unclear' or previously_deferred:
        q['answer_status'] = 'needs_review'
        q['answer'] = ''
    q['review_note'] = ' '.join(issues) or (q.get('review_note', '') if previously_deferred else '')
    return q
