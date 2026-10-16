"""Grant/revoke an existing account; never use username alone as a runtime role."""
import argparse
from app import create_app
from app.database import db
from app.models.user import User
from app.models.admin import AdminRole

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['grant', 'revoke'])
    parser.add_argument('username')
    args = parser.parse_args()
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(username=args.username).first()
        if not user:
            raise SystemExit('Account not found; register the account first.')
        role = db.session.get(AdminRole, user.id)
        if args.action == 'grant' and not role:
            db.session.add(AdminRole(user_id=user.id))
        elif args.action == 'revoke' and role:
            db.session.delete(role)
        db.session.commit()
        print('Administrator role updated for:', user.username)
