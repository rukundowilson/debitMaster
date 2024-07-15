from flask import Flask, render_template, request, redirect, flash, session
import pymysql
from urllib.parse import quote
import re
import bcrypt
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user
import datetime

app = Flask(__name__)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

app.config['SECRET_KEY'] = 'jar'

# MySQL connection
def get_db_connection():
    return pymysql.connect(
        host='localhost',
        user='wilson',
        password='468161Ro@',
        db='trademonitor'
    )

@app.route("/")
def index():
    session.clear()
    return render_template("index.html")

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT id, username, email FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    connection.close()

    if user:
        return User(id=user[0], username=user[1], email=user[2])
    return None

# Complete login logic
@app.route('/login', methods=['POST', 'GET'])
def login():
    session.clear()
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        if not email or not password:
            flash("Invalid email or password")
            return redirect('/login')

        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            # Check if the email exists
            poke_email = "SELECT email FROM users WHERE email = %s"
            cursor.execute(poke_email, (email,))
            email_exist = cursor.fetchone()

            if not email_exist:
                flash("Your email does not match any of our records. You can register with it.", 'error')
                return redirect('/login')

            # Retrieve the hashed password from the database
            query = "SELECT id, hash, username FROM users WHERE email = %s"
            cursor.execute(query, (email,))
            result = cursor.fetchone()
            user_id = result[0]
            hashedpwd = result[1]
            username = result[2]

            # Verify the provided password against the hashed password
            if bcrypt.checkpw(password.encode('utf-8'), hashedpwd.encode('utf-8')):
                flash("Welcome back!", 'success')
                # Set session or any other logic for a logged in user
                session['user_id'] = user_id
                print(f"Logged in as {session['user_id']}")
                login_user(User(user_id, username, email))

                return redirect('/dashboard')
            else:
                flash("Invalid email or password", 'error')

        except pymysql.MySQLError as e:
            print(f"Error: {e}")
            if connection:
                connection.rollback()
        finally:
            cursor.close()
            connection.close()

    return render_template('login.html')

# show dashboard info
@app.route('/dashboard',methods=['GET'])
@login_required
def user_profile():
    # establish server connection
    connection=get_db_connection()
    cursor=connection.cursor()

    query1='SELECT username FROM users WHERE id = %s '
    cursor.execute(query1,(session['user_id']))
    username=cursor.fetchone()[0]
    
    # retrive recepient,amount and when
    get_logs='SELECT amount,recipient,show_time_offerered FROM debit WHERE user_id= %s '
    cursor.execute(get_logs,(session['user_id']))
    show_logs=cursor.fetchall()
    print(show_logs)
    paymode='debit'

    # display total debits
    get_total_debit='SELECT SUM(amount) FROM debit WHERE user_id = %s '
    cursor.execute(get_total_debit,session['user_id'])
    total_debit=cursor.fetchone()[0]
    print(total_debit)

    # loop through all records to retrive recepient,amount and when
    return render_template('portfolio.html',
                            username=username,
                            paymode=paymode,
                            show_logs=show_logs,
                            total_debit=total_debit
                            )


# Manage debit provision
@app.route('/debit', methods=['GET', 'POST'])
@login_required
def debit_provider():
    # Establish database connection
    connection = get_db_connection()
    cursor = connection.cursor()

    # display total debits
    get_total_debit='SELECT SUM(amount) FROM debit WHERE user_id = %s '
    cursor.execute(get_total_debit,session['user_id'])
    total_debit=cursor.fetchone()[0]
    print(total_debit)
    
    #define user identity with user name 
    query1='SELECT username FROM users WHERE id = %s '
    cursor.execute(query1,(session['user_id']))
    username=cursor.fetchone()[0]
    if request.method == 'POST':
        recipient = request.form.get('name-to')
        amount = request.form.get('amount')
        payback_time = request.form.get('payback') or None

        # web view time format
        now=datetime.datetime.now()
        day=now.day
        month=now.month
        year=now.year
        deal_time=f'{day}' + '-' + f'{month}' + '-' + f'{year}'
        
        if not recipient or not amount:
            flash("All fields are required")
            return redirect("/debit")

        try:
            amount = float(amount)
        except ValueError:
            flash("You must provide a number as amount")
            return redirect('/debit')

        try:
            # Insert debit record
            query = 'INSERT INTO debit (user_id, recipient, amount, timestamp, payback_time_expected,show_time_offerered) VALUES (%s, %s, %s, %s, %s,%s)'
            cursor.execute(query, (session['user_id'], recipient, amount, datetime.datetime.now(), payback_time,deal_time))
            connection.commit()

            flash("Debit record added successfully", 'success')
            return redirect('/dashboard')
        except pymysql.MySQLError as error:
            print(f"Error: {error}")
            flash("An error occurred while processing your request", 'danger')
            if connection:
                connection.rollback()
        finally:
            cursor.close()
            connection.close()

    return render_template('debit.html',username=username,total_debit=total_debit)

# Allow user to logout
@app.route('/logout')
@login_required
def logout():
    session.clear()  # Clears all session data
    logout_user()
    return redirect('/')
  

# Allow users to register and manage session
@app.route('/register', methods = ['POST', 'GET'])
def register():
    session.clear()
    if request.method == 'POST':
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form['password']
        check_password = request.form['check-password']

        # Basic validation
        if not username or not email or not password or not check_password:
            flash("All fields are required", "warning")
            return redirect('/register')

        # Email format validation using regex
        email_regex = r"[^@]+@[^@]+\.[^@]+"
        if not re.match(email_regex, email):
            flash("Invalid email address", "warning")
            return redirect('/register')

        # Password and confirmation validation
        if password != check_password:
            flash("Passwords do not match", "warning")
            return redirect('/register')

        if len(password) <= 4:
            flash("Password must be longer than 4 characters", "warning")
            return redirect('/register')

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            # Check if email already exists
            cursor.execute("SELECT email FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                flash("User with this email already exists", "warning")
                return redirect('/register')

            # Insert the new user into the database
            query = "INSERT INTO users (username, email, hash) VALUES (%s, %s, %s)"
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor.execute(query, (username, email, hashed_password))
            connection.commit()

            flash("You are registered successfully", "success")
            return redirect('/login')
        except pymysql.MySQLError as e:
            print(f"Error: {e}")
            if connection:
                connection.rollback()
            flash("An error occurred while processing your request", "danger")
        finally:
            cursor.close()
            connection.close()

    return render_template("register.html")

if __name__ == "__main__":
    app.run(debug=True)
