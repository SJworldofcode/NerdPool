# template_helpers.py
"""
Helper functions to ensure consistent template context across all routes.
This ensures the navbar always has the necessary variables to display properly.
"""
from flask import session
from db import get_db

def get_navbar_context():
    """
    Returns a dict with all context variables needed for the navbar to render properly.
    Should be called by every route that renders a template with BASE_TMPL.
    
    Returns:
        dict: {
            'carpool_options': list of {id, name} dicts for carpool selector,
            'is_admin': bool indicating if current user is admin
        }
    """
    db = get_db()
    user_id = session.get("user_id")
    is_admin = bool(session.get("is_admin"))
    
    carpool_options = []
    
    # Check if multi-carpool mode is available
    try:
        # Check if the necessary tables exist
        tables = db.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN ('carpools', 'carpool_memberships')
        """).fetchall()
        
        if len(tables) == 2 and user_id:
            # Fetch user's carpools
            carpool_options = db.execute("""
                SELECT c.id, c.name
                FROM carpools c
                JOIN carpool_memberships cm ON cm.carpool_id = c.id
                WHERE cm.user_id = ? AND cm.active = 1
                ORDER BY c.name
            """, (user_id,)).fetchall()
    except Exception:
        # If there's any error (e.g., tables don't exist), just return empty list
        pass
    
    return {
        'carpool_options': carpool_options,
        'is_admin': is_admin
    }
