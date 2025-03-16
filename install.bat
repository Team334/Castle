@echo off
echo Setting up the Scouting-App...

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed! Please install Python 3.7+ and try again.
    exit /b 1
)

:: Create and activate virtual environment
echo Creating virtual environment...
python -m venv venv
call venv\Scripts\activate

:: Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

:: Install requirements
echo Installing required packages...
pip install -r requirements.txt

echo.
echo Installation complete! You can now run the app with:
echo     python app\main.py
echo.
echo Don't forget to set up your environment variables if needed. 