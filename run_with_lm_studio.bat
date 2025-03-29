@echo off
:: Sample batch file to run the Article Monitor & Rewriter with LM Studio
echo Starting Article Monitor & Rewriter with LM Studio...

:: Make sure LM Studio server is running before executing this script!
python main.py --lm-studio-model mistral-7b-instruct-v0.3 --limit 3 --skip-wordpress

echo Done!
pause 