from flask import Flask, render_template, request, redirect, url_for, session
from auth import login_user

app = Flask(__name__)

app.secret_key = "cruise-secret-key"


@app.route("/")
def home():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        user = login_user(email, password)

        if user:

            session["user_id"] = user["user_id"]
            session["name"] = user["name"]
            session["role"] = user["role"]

            return redirect(url_for("dashboard"))

        return "Invalid email or password"

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    role = session["role"]

    if role == "ADMIN":
        return "Welcome Admin"

    elif role == "AGENT":
        return "Welcome Agent"

    elif role == "CUSTOMER":
        return "Welcome Customer"

    return "Unknown role"


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)