import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    users = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
    purchases = db.execute("SELECT * FROM portfolio WHERE id = ?", session["user_id"])
    totalcash = users[0]["cash"]
    for purchase in purchases:
        totalcash += purchase["total"]
    return render_template(
        "index.html", purchases=purchases, users=users, totalcash=totalcash
    )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        symbolvalues = lookup(request.form.get("symbol"))
        shares = request.form.get("shares")
        if not shares.isdigit():
            return apology("Not a digit")
        else:
            shares = float(shares)
        if shares < 0.0:
            return apology("Need more shares bud", 400)
        elif not request.form.get("shares"):
            return apology("You need more shares champ", 400)
        elif symbolvalues == None:
            return apology("Symbol DNE", 400)
        elif shares * symbolvalues['price'] > cash[0]["cash"]:
            return apology("Not enough cash", 400)
        elif shares % 1 != 0:
            return apology("No fractions", 400)
        else:
            # update stock history
            cost = cash[0]["cash"] - shares * symbolvalues['price']
            total = shares * symbolvalues['price']
            db.execute("INSERT into PURCHASES (ID_user, symbol, shares, price, total) VALUES (?, ?, ?, ?, ?)", session["user_id"], symbolvalues['symbol'], shares, symbolvalues['price'], total)
            db.execute("UPDATE users SET cash = ? WHERE id = ?", cost, session["user_id"])

            # add stock to portfolio
            portfolio = db.execute("SELECT * FROM portfolio WHERE id = ? AND symbol = ?", session["user_id"], symbolvalues['symbol'])
            if portfolio:
                #update stock in portfolio
                portfolio = db.execute("SELECT * FROM portfolio WHERE id = ? AND symbol = ?", session["user_id"], symbolvalues['symbol'])
                db.execute("UPDATE portfolio SET (shares, total) = (?, ?) WHERE id = ? AND symbol = ?", (shares + portfolio[0]['shares']), (total + portfolio[0]['total']), session['user_id'], symbolvalues['symbol'])
            else:
                db.execute("INSERT INTO portfolio (id, symbol, shares, price, total) VALUES (?, ?, ?, ?, ?)", session["user_id"], symbolvalues['symbol'], shares, symbolvalues['price'], total)
            return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    purchases = db.execute("SELECT * FROM purchases WHERE ID_user = ?", session["user_id"])
    return render_template("history.html", purchases=purchases)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if lookup(symbol) == None:
            return apology("symbol doesn't exist", 400)
        else:
            temp = lookup(symbol)
            return render_template("quoted.html", name=temp['name'], price=temp['price'], symbol=temp['symbol'])
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        usercheck = db.execute("SELECT username FROM users WHERE username = ?", request.form.get("username"))
        if not usercheck:
            tempuser = "random"
        else:
            tempuser = usercheck[0]['username']
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)
        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        # Ensure confirmatino was submitted
        elif not request.form.get("confirmation"):
            return apology("must provide confirmation", 400)
        elif username == tempuser:
            return apology("username already exists", 400)
        elif password != confirmation:
            return apology("passwords do not match", 400)
        else:
            password = generate_password_hash(password)
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, password)
            # Remember which user has logged in
            rows = db.execute("SELECT * FROM users WHERE username = ?", username)
            session["user_id"] = rows[0]['id']
            # Redirect user to home page
            return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        portfolio = db.execute("SELECT * FROM portfolio WHERE id = ?", session["user_id"])
        temp = db.execute("SELECT shares FROM portfolio WHERE id = ? AND symbol = ?", session["user_id"], request.form.get("symbol"))
        if not request.form.get("symbol"):
            return apology("PICK A SYMBOL", 400)
        elif int(request.form.get("shares")) <= 0:
            return apology("Need positive # of shares", 400)
        elif int(request.form.get("shares")) > temp[0]['shares']:
            return apology("Too many shares", 400)
        else:
            value = lookup(request.form.get("symbol"))
            shares = int(request.form.get("shares"))
            total = (shares * value['price'])
            portfolio = db.execute("SELECT * FROM portfolio WHERE id = ? AND symbol = ?", session["user_id"], value['symbol'])
            db.execute("UPDATE portfolio SET (shares, total) = (?, ?) WHERE id = ? AND symbol = ?", (portfolio[0]['shares'] - shares), (portfolio[0]['total'] - total), session['user_id'], value['symbol'])
            # If no shares of that kind left
            portfolio = db.execute("SELECT * FROM portfolio WHERE id = ? AND symbol = ?", session["user_id"], value['symbol'])
            if portfolio[0]['shares'] == 0:
                db.execute("DELETE FROM portfolio WHERE id = ? AND symbol = ?", session["user_id"], value['symbol'])
            #Update purchases
            db.execute("INSERT INTO purchases (ID_user, symbol, shares, price, total) VALUES (?, ?, ?, ?, ?)", session['user_id'], value['symbol'], -1*shares, value['price'], total)
            #Update User
            db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", total, session['user_id'])
            return redirect("/")
    else:
        purchases = db.execute("SELECT * FROM portfolio WHERE id = ?", session["user_id"])
        return render_template("sell.html", purchases=purchases)


@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addcash():
    if request.method == "POST":
        cash = int(request.form.get("Cash"))
        if cash > 0 and cash < 5000:
            db.execute("UPDATE users SET cash = ? + cash WHERE id = ?", cash, session["user_id"])
            return redirect("/")
        else:
            return apology("Cash needs to be positive or less than 5000", 400)
    else:
        return render_template("addcash.html")
