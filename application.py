import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd


# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set

if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session["user_id"]
    count_items = db.execute("SELECT  COALESCE(count(shares), 0) as total_shares FROM transactions WHERE user_id = ?",user_id)
    query = """Select * from (SELECT 
	user_id,
	symbol, 
	name,
	price,
	SUM(shares) as total_shares 
FROM transactions  
GROUP BY symbol) WHERE 
	user_id = ?"""
    #"""SELECT symbol, name, COALESCE(price,0) as price, COALESCE(SUM(shares), 0) as total_shares FROM transactions WHERE user_id = ?"""
    stocks = db.execute(query, user_id)
    cash = db.execute("SELECT cash FROM user WHERE id = ?", user_id)[0]["cash"]

    total = cash
    if count_items[0]["total_shares"]>0:
        for stock in stocks:
            total += stock["price"] * stock["total_shares"]
    else:
        stocks = []


    return render_template("index.html", stocks=stocks, cash=cash, usd=usd)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        item = lookup(symbol)

        if not symbol:
            return apology("Not any symbol")
        elif not item:
            return apology("Haven't this symbol")

        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("Shares must be a positive integer")

        if shares <= 0:
            return apology("Shares must be a positive!!!! integer")

        user_id = session["user_id"]
        cash = db.execute("SELECT cash FROM user WHERE id = ?", user_id)[0]['cash']

        i_name = item["name"]
        i_price = item["price"]
        total_price = i_price * shares

        if cash < total_price:
            return apology("You haven't got enough money")
        else:
            db.execute("UPDATE user SET cash = ? WHERE id = ?", cash - total_price, user_id)
            db.execute("INSERT INTO transactions (user_id, name, shares, price, symbol, type) VALUES (?, ?, ?, ?, ?, ?)", user_id, i_name, shares, i_price, symbol,'buy', )


        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    transactions = db.execute("SELECT shares, price, symbol, type, time FROM transactions WHERE user_id = ?", user_id)




    return render_template("history.html", transactions=transactions, usd=usd)

def is_provided(field):
    if not request.form.get(field):
        return apology(f"must provide {field}", 403)

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
        rows = db.execute("SELECT * FROM user WHERE username = :username",
                          username=request.form.get("username"))

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
    """Get stock quote"""

    if request.method == "POST":
        symbol = request.form.get("symbol")

        if not symbol:
            return apology("Please enter a symbol!")
        item = lookup(symbol)

        if not item:
            return apology("Incorrect Symbol. Try again")

        return render_template("quote2.html", item=item)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    """Register users"""

    if (request.method == "POST"):
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return apology("Must provide username", 400)
        elif not password:
            return apology("Must provide password", 400)
        elif not confirmation:
            return apology("Must provide confirmation", 400)
        elif password != confirmation:
            return apology("Passwords do not the same with confirmation", 400)

        #хэш для пароля и сохранение нового юзера в базу данных
        hash = generate_password_hash(password)


        #проверка что нет такого в базе
        try:
            db.execute("INSERT INTO user (username, hash) VALUES (?, ?)", username, hash)

            #direct user to home page
            return redirect("/")
        except:
            return apology("This username has already", 400)

        session["user_id"] = db.execute("INSERT INTO user (username, hash) VALUES (?, ?)", username, hash)

        return redirect("/")

    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    username = db.execute("SELECT username FROM user WHERE id = :ids", ids = session["user_id"])
    #replace dashboard on transactions
    tmp = db.execute("SELECT symbol FROM transactions WHERE user_id = :ids",
                        ids = session["user_id"])

    if request.method == "POST":
        user_id = session["user_id"]
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        if shares < 0:
            return apology("Shares must be a positive integer")

        i_price = lookup(symbol)['price']
        i_name = lookup(symbol)['name']
        price = shares * i_price
        balance_s = db.execute("SELECT  Sum(shares) as shares FROM transactions WHERE user_id = ? AND symbol = ? GROUP BY symbol", user_id,symbol)[0]["shares"]

        if balance_s < shares:
            return apology("Haven't enough shares")
        balance = db.execute("SELECT cash FROM user WHERE id = ?", user_id)[0]["cash"]
        db.execute("UPDATE user SET cash = ? WHERE id = ?", balance + price, user_id)
        db.execute("INSERT INTO transactions (user_id, name, shares , price, symbol, type) VALUES (?, ?, ?, ?, ?, ?)", user_id, i_name, -shares, i_price, symbol,"sell")
        return redirect("/")
    else:
        user_id = session["user_id"]
        symbol = db.execute("SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)
        return render_template("sell.html", symbol=symbol)



def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)