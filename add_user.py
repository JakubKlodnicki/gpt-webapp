from getpass import getpass
import os
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv
from app import app, db, User  # Importujemy również instancję aplikacji

load_dotenv()

def add_user():
    username = input('Enter username: ')
    password = getpass('Enter password: ')
    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

    # Sprawdzenie, czy użytkownik już istnieje
    if User.query.filter_by(username=username).first():
        print(f'User {username} already exists.')
        return

    new_user = User(username=username, password=hashed_password)
    db.session.add(new_user)
    db.session.commit()
    print(f'User {username} has been created successfully.')

if __name__ == '__main__':
    with app.app_context():  # Używamy kontekstu aplikacji bezpośrednio z instancji aplikacji
        add_user()
