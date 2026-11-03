AI Warranty Defect Classifier MVP

Setup:
1. Install requirements:
   pip install -r requirements.txt

2. Make sure Ollama is running:
   ollama serve

3. Pull a model:
   ollama pull llama3
   or
   ollama pull llama3.2:3b

4. Optional SQL environment variables:
   set SQL_SERVER=Hvac-phdb-db.apps.carrier.com
   set SQL_DATABASE=CarrierAnalytics
   set SQL_UID=your_user
   set SQL_PWD=your_password
   set SQL_DRIVER=ODBC Driver 17 for SQL Server

5. Run app:
   python app.py

6. Open:
   http://127.0.0.1:5000

Notes:
- Use "Load Sample Claim" first to test without SQL.
- AI labels are not final labels. Review and save final labels before exporting.
