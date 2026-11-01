# Generic Kaggle runner: copy the repo from the attached dataset to /tmp, then execute kaggle/tasks.sh
# (which builds envs, fetches weights and runs whatever the current phase needs). Artefacts -> /kaggle/working.
import glob, os, shutil, subprocess

hits = glob.glob("/kaggle/input/**/kaggle/tasks.sh", recursive=True)
if not hits:
    z = glob.glob("/kaggle/input/**/*.zip", recursive=True)[0]
    shutil.unpack_archive(z, "/tmp/s2s_src"); hits = glob.glob("/tmp/s2s_src/**/kaggle/tasks.sh", recursive=True)
src = os.path.dirname(os.path.dirname(hits[0]))
R = "/tmp/s2s/repo"
shutil.copytree(src, R, dirs_exist_ok=True)
rc = subprocess.call(["bash", f"{R}/kaggle/tasks.sh"], cwd=R)
print("TASKS EXIT", rc)
