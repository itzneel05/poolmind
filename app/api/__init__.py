"""
poolmind REST API — Blueprint registration.
"""

from flask import Blueprint

api = Blueprint("api", __name__, url_prefix="/api")


def register_blueprints(app):
    from app.api.resources import resources_bp
    from app.api.ingest import ingest_bp
    from app.api.search import search_bp
    from app.api.browse import browse_bp
    from app.api.intelligence import intelligence_bp
    from app.api.maintenance import maintenance_bp
    from app.api.ai_prompts import ai_bp
    from app.api.settings import settings_bp

    app.register_blueprint(resources_bp)
    app.register_blueprint(ingest_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(browse_bp)
    app.register_blueprint(intelligence_bp)
    app.register_blueprint(maintenance_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(api)
