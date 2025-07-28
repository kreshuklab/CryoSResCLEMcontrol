call "C:/Users/mojiri/AppData/Local/anaconda3/condabin/activate.bat"
cd C:/Users/mojiri/CryoSResCLEMcontrol
set QT_PLUGIN_PATH=%CONDA_PREFIX%\library\plugins
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /format:list') do set datetime=%%I
conda run -n CryoSResCLEMcontrol_env python microscope_control.py > focus_lock_%datetime:~0,8%-%datetime:~8,6%.log 2>&1
