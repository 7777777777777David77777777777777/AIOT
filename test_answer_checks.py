import unittest
from app.answer_checks import check_question


class AnswerCheckTests(unittest.TestCase):
    def q(self, question='計算結果', solution='代入得 2', answer='2'):
        return dict(question=question,solution=solution,answer=answer,clarity='clear')

    def test_admitted_uncertainty_is_not_a_final_answer(self):
        q=check_question(self.q(solution='此處字形模糊，暫以常見詞義作答。',answer='略'))
        self.assertEqual(q['answer_status'],'needs_review')
        self.assertEqual(q['answer'],'')
        self.assertIn('字形模糊',q['solution'])

    def test_count_real_regression_without_trusting_quote_source(self):
        q=check_question(self.q(question='以原文默出共有幾字？',solution='「臣無祖母，無以至今日；祖母無臣，無以終餘年。」共20字。',answer='D'))
        self.assertEqual(q['count_checks'][0]['count'],18)
        self.assertEqual(q['answer'],'')
        self.assertEqual(check_question(q),q)

    def test_normal_derivation_is_preserved_but_not_claimed_verified(self):
        q=check_question(self.q())
        self.assertEqual(q['answer'],'2')
        self.assertEqual(q['answer_status'],'unverified')

    def test_missing_solution_defers_answer(self):
        q=check_question(self.q(solution=''))
        self.assertEqual(q['answer_status'],'needs_review')
        self.assertIn('沒有解題說明',q['review_note'])

    def test_does_not_flag_normal_mathematical_uncertainty_question(self):
        q=check_question(self.q(question='某事件發生的機率為何？',solution='事件機率為 $1/2$。',answer='$1/2$'))
        self.assertEqual(q['answer_status'],'unverified')
