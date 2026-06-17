# app.py
"""
로컬 웹 서버. web/index.html을 띄우고, 입력을 받아 파이프라인을 실행한다.
실행: python app.py  →  브라우저에서 http://127.0.0.1:5000 접속
"""
from flask import Flask, request, jsonify, send_from_directory
import config
from orchestrator import run_pipeline
from tools import wiki_utils, pdf_export
from tools import macro_collector

app = Flask(__name__, static_folder="web", static_url_path="")


@app.route("/")
def index():
    return send_from_directory("web", "index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    company = (data.get("company") or "").strip()
    year = int(data.get("year") or 2023)

    if not company:
        return jsonify({"success": False, "reason": "회사명이 비어 있습니다."})

    macro = macro_collector.collect_macro(base_rate="3.50%")

    try:
        result = run_pipeline(company, year, sector="", macro=macro)  # sector 빈 문자열
    except Exception as e:
        return jsonify({"success": False, "reason": str(e)})

    if not result["success"]:
        return jsonify({"success": False, "reason": result["reason"]})

    report_md = wiki_utils.read_page("overview")
    out_path = pdf_export.export(report_md, company, year)
    metrics = result.get("metrics", {})
    return jsonify({
        "success": True,
        "grade": metrics.get("grade", "N/A"),
        "opinion": metrics.get("opinion", "N/A"),
        "report_url": f"/output/{out_path.name}",
    })



@app.route("/output/<path:filename>")
def serve_output(filename):
    return send_from_directory(config.OUTPUT_DIR, filename)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
