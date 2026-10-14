# Open only the EPCC instance. No terminal required on Windows.
import os,runpy,sys
from pathlib import Path
root=Path(__file__).resolve().parent
os.environ['RVVLAB_STUDIO_TARGET']='EPCC'
sys.path.insert(0,str(root/'studio'))
runpy.run_path(str(root/'studio'/'RVV_Lab_Studio.pyw'),run_name='__main__')
