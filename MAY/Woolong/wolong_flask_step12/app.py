from flask import Flask, jsonify, render_template, request

from services.calculation_service import run_calculation
from services.output_builder import build_output
from services.validation import validate_csv_text


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        return render_template("info_plate.html", result=None)

    @app.post("/calculate")
    def calculate():
        model_number = request.form.get("model_number", "")
        result = run_calculation(model_number)
        return render_template("info_plate.html", result=build_output(result))


    @app.get("/validate")
    def validate_form():
        return render_template("validation.html", run=None)

    @app.post("/validate")
    def validate_upload():
        uploaded = request.files.get("validation_csv")
        tolerance = float(request.form.get("tolerance", "0.01") or 0.01)
        if not uploaded:
            return render_template("validation.html", run={"status": "empty", "cases": [], "message": "Upload a CSV file first."})
        csv_text = uploaded.read().decode("utf-8-sig")
        run = validate_csv_text(csv_text, tolerance=tolerance)
        return render_template("validation.html", run=run.to_dict())

    @app.post("/api/validate")
    def api_validate():
        payload = request.get_json(silent=True) or {}
        csv_text = payload.get("csv_text", "")
        tolerance = float(payload.get("tolerance", 0.01))
        run = validate_csv_text(csv_text, tolerance=tolerance)
        return jsonify(run.to_dict())

    @app.post("/api/calculate")
    def api_calculate():
        payload = request.get_json(silent=True) or {}
        model_number = payload.get("model_number", request.form.get("model_number", ""))
        result = run_calculation(model_number)
        return jsonify(build_output(result))

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
