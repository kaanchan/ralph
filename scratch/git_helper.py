import subprocess
import os

def run_and_save(cmd, filename):
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    with open(f"scratch/{filename}", "w", encoding="utf-8") as f:
        f.write(f"STDOUT:\n{result.stdout}\n")
        f.write(f"STDERR:\n{result.stderr}\n")

os.makedirs("scratch", exist_ok=True)
run_and_save(["git", "status"], "git_status.txt")
run_and_save(["git", "log", "-n", "5"], "git_log.txt")
