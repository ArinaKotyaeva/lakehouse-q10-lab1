import sys,time,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_lab import query
for i in range(60):
    try:
        query('SELECT 1','bi_readiness'); break
    except Exception:
        if i==59: raise
        time.sleep(2)
subprocess.run(['docker','compose','exec','-T','bi','python','/app/check_app.py'],check=True,cwd=Path(__file__).resolve().parents[1])
