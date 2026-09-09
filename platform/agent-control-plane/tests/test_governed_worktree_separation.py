import json
from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class GovernedWorktreeSeparationTests(unittest.TestCase):
    def test_primary_vscode_window_hides_delivery_worktrees_and_starts_at_root(self):
        settings = json.loads(
            (REPOSITORY_ROOT / ".vscode" / "settings.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertIs(settings["git.detectWorktrees"], False)
        self.assertEqual(settings["terminal.integrated.cwd"], "${workspaceFolder}")

    def test_model_facing_skills_prohibit_jira_implementation_on_workbench(self):
        skills = REPOSITORY_ROOT / "platform" / "agent-control-plane" / "agent-assets" / "skills"
        delivery = (skills / "deliver-governed-change" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        git_workflow = (skills / "manage-git-workflow" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        delivery = " ".join(delivery.split())
        git_workflow = " ".join(git_workflow.split())

        self.assertIn(
            "Do not continue the Jira-scoped implementation on `workbench/local`.",
            delivery,
        )
        self.assertIn(
            "Never switch that checkout to `main` or a Jira-keyed branch",
            git_workflow,
        )


if __name__ == "__main__":
    unittest.main()
