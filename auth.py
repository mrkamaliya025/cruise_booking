from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db_connection


def create_user(name, email, password, role):

    connection = get_db_connection()
    cursor = connection.cursor()

    password_hash = generate_password_hash(password)

    query = """
        INSERT INTO users
        (name, email, password_hash, role)
        VALUES (%s, %s, %s, %s)
    """

    cursor.execute(
        query,
        (name, email, password_hash, role)
    )

    connection.commit()

    cursor.close()
    connection.close()


def login_user(email, password):

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    query = """
        SELECT *
        FROM users
        WHERE email = %s
        AND status = 'ACTIVE'
    """

    cursor.execute(query, (email,))

    user = cursor.fetchone()

    cursor.close()
    connection.close()

    if user and check_password_hash(
        user["password_hash"],
        password
    ):
        return user

    return None