from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / ".github" / "scripts" / "issue_triage.py"
CONFIG_PATH = ROOT / ".github" / "issue-triage-config.json"

spec = importlib.util.spec_from_file_location("issue_triage", SCRIPT_PATH)
assert spec is not None
issue_triage = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = issue_triage
spec.loader.exec_module(issue_triage)


class IssueTriageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = issue_triage.read_json(CONFIG_PATH)

    def test_parse_model_json_strips_code_fence(self) -> None:
        payload = "```json\n{\"summary\":\"ok\",\"issueType\":\"bug\"}\n```"
        parsed = issue_triage.parse_model_json(payload)
        self.assertEqual(parsed["summary"], "ok")
        self.assertEqual(parsed["issueType"], "bug")

    def test_similarity_score_prefers_near_duplicates(self) -> None:
        left = {
            "title": "screenshot cubemap produces 6 almost identical images",
            "body": "screenshot cubemap saves six front images on Linux Mint with r_fullscreen 0",
        }
        right = {
            "title": "cubemap screenshots save the same face six times",
            "body": "Using screenshot cubemap on Linux produces six front shots instead of front/back/left/right/top/bottom.",
        }
        other = {
            "title": "OpenAL device recovery request",
            "body": "Audio device reconnect should not require snd_restart.",
        }
        self.assertGreater(issue_triage.similarity_score(left, right), issue_triage.similarity_score(left, other))

    def test_validate_model_result_only_closes_high_confidence_duplicates(self) -> None:
        result = {
            "summary": "duplicate",
            "issueType": "duplicate",
            "componentLabel": "component:screenshots",
            "severity": "",
            "detectedPoints": ["same cubemap behavior"],
            "missingInfo": [],
            "answers": [],
            "needsHumanReview": False,
            "needsInfo": False,
            "appearsActionable": False,
            "shouldSplit": False,
            "fullDuplicate": True,
            "duplicateConfidence": 0.95,
            "relatedIssues": [
                {
                    "issueNumber": 3,
                    "relation": "full duplicate",
                    "sharedPoints": ["cubemap saves the same face six times"],
                    "reason": "The reproduction and outcome match.",
                    "confidence": 0.95,
                }
            ],
            "suggestedLabels": [{"name": "duplicate", "reason": "same report"}],
            "planSteps": [],
        }
        validated = issue_triage.validate_model_result(
            result,
            config=self.config,
            allowed_labels={"duplicate", "component:screenshots", "needs-human-review"},
            duplicate_candidates=[{"number": 3}],
        )
        self.assertTrue(validated["shouldCloseDuplicate"])
        self.assertFalse(validated["needsHumanReview"])

    def test_build_comment_uses_required_sections(self) -> None:
        analysis = {
            "summary": "Cube-map screenshots appear to repeat the front face.",
            "issueType": "bug",
            "componentLabel": "component:screenshots",
            "severity": "",
            "detectedPoints": ["`screenshot cubemap` saves repeated front images."],
            "missingInfo": ["A matching screenshot set from the current build."],
            "answers": ["The screenshot guide says cube-map captures should write six named faces."],
            "needsHumanReview": False,
            "needsInfo": True,
            "appearsActionable": True,
            "shouldSplit": False,
            "fullDuplicate": False,
            "duplicateConfidence": 0.0,
            "shouldCloseDuplicate": False,
            "relatedIssues": [],
            "suggestedLabels": [],
            "planSteps": ["Reproduce the cubemap capture.", "Inspect face naming and capture rotation.", "Add or update a focused regression check."],
        }
        comment = issue_triage.build_comment(
            analysis,
            {
                "type:bug": "Detected main issue type: bug.",
                "component:screenshots": "Issue text and repository context point to this component.",
                "needs-info": "Critical reproduction or environment details are still missing.",
            },
        )
        self.assertIn("## Summary", comment)
        self.assertIn("## Detected points", comment)
        self.assertIn("## Status", comment)
        self.assertIn("needs more information", comment.lower())


if __name__ == "__main__":
    unittest.main()
