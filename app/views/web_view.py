import os
from flask import Blueprint, redirect, abort
web_bp = Blueprint("web", __name__)
@web_bp.route("/")
def index():
    return redirect(os.environ.get("FRONTEND_URL", "http://127.0.0.1:5000"))
@web_bp.route("/admin/db")
def view_database():
    abort(404)
