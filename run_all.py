# run_all.py
import subprocess

subprocess.Popen("uvicorn app.main:app --reload", shell=True)
subprocess.Popen("cd frontend && npm run dev", shell=True)

input("Press ENTER to stop...")