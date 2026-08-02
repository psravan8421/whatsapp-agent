import os
import logging
from pathlib import Path
import subprocess

logger = logging.getLogger(__name__)

class GitHubHandler:
    def __init__(self, repo_url, token):
        self.repo_url = repo_url
        self.token = token
        self.repo_dir = Path("/home/ubuntu/repos/whatsapp-agent")

    def sync(self, output_file):
        if not self.token:
            logger.warning("GITHUB_TOKEN not set. Skipping GitHub sync.")
            return False
            
        try:
            # We assume the repo is already cloned by Devin in /home/ubuntu/repos/whatsapp-agent
            # If not, we would clone it here.
            
            # Copy output to repo
            target_output = self.repo_dir / "dataset" / "output.csv"
            target_output.parent.mkdir(parents=True, exist_ok=True)
            
            # Read output and write to target
            with open(output_file, 'r') as f_in:
                with open(target_output, 'w') as f_out:
                    f_out.write(f_in.read())
            
            # Also copy code updates
            code_src = Path("/home/ubuntu/whatsapp-agent/code")
            code_dest = self.repo_dir / "code"
            code_dest.mkdir(exist_ok=True)
            for f in code_src.glob("*.py"):
                with open(f, 'r') as f_in:
                    with open(code_dest / f.name, 'w') as f_out:
                        f_out.write(f_in.read())
            
            # Git operations
            cmds = [
                ["git", "add", "."],
                ["git", "commit", "-m", "Built AI Message Router with multimodal intelligence"],
                ["git", "push"]
            ]
            
            for cmd in cmds:
                result = subprocess.run(cmd, cwd=self.repo_dir, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"Git command failed: {' '.join(cmd)}")
                    logger.error(result.stderr)
                    return False
            
            logger.info("Successfully pushed updates to GitHub.")
            return True
            
        except Exception as e:
            logger.error(f"GitHub sync failed: {str(e)}")
            return False
