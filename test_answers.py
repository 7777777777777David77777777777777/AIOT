import json
import unittest
from app.answers import parse_answer, stored_answer, answer_text


class AnswerContractTests(unittest.TestCase):
    def question(self, **changes):
        return dict(number="第 2 題", question="求 x", clarity="clear", solution="$x=2$", answer="2",
                    unclear_reason="", recapture_hint="", photo_indices=[1], **changes)

    def test_unclear_cannot_publish_guessed_answer(self):
        q = self.question()
        q.update(clarity="unclear", unclear_reason="右側條件被裁切", recapture_hint="補拍照片 1 右側")
        data = parse_answer(json.dumps({"questions": [q]}), 1)
        self.assertEqual(data["questions"][0]["answer"], "")
        self.assertEqual(data["questions"][0]["solution"], "")
        self.assertIn("右側條件被裁切", answer_text(data))
        self.assertEqual(stored_answer(json.dumps(data)), data)

    def test_invalid_contract_rejected(self):
        for change in ({"photo_indices": [2]}, {"answer": ""}, {"clarity": "maybe"}):
            q = self.question(); q.update(change)
            with self.assertRaises(ValueError):
                parse_answer(json.dumps({"questions": [q]}), 1)
        with self.assertRaises(ValueError):
            parse_answer("答案是 2", 1)
        self.assertIsNone(stored_answer("舊版 Markdown"))


if __name__ == "__main__":
    unittest.main()
