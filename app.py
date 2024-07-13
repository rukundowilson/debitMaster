from flask import Flask, render_template, request, redirect, flash,session
import pymysql
from urllib.parse import quote
import re
import bcrypt

app = Flask(__name__)

# Password containing special characters
password = '468161Ro@'
encoded_password = quote(password)

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
    return render_template("index.html")

# complete login logic
@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        try:
            # Check if the email exists
            poke_email = "SELECT email FROM users WHERE email = %s"
            cursor.execute(poke_email, (email,))
            email_exist = cursor.fetchone()
            
            if not email_exist:
                flash("Your email does not match any of our records. You can register with it.",'error')
                return redirect('/login')
            
            # Retrieve the hashed password from the database
            query = "SELECT hash FROM users WHERE email = %s"
            cursor.execute(query, (email,))
            result = cursor.fetchone()
            hashedpwd = result[0]
            
            # Verify the provided password against the hashed password
            if bcrypt.checkpw(password.encode('utf-8'), hashedpwd.encode('utf-8')):
                flash("Welcome back!",'success')
                # Set session or any other logic for a logged in user
                check_session=" SELECT id FROM users WHERE email = %s "
                cursor.execute(check_session,(email))
                user_id=cursor.fetchone()[0]

                if user_id:
                    # set user login session
                    session['user_id'] = user_id
                    print(f"loged in as {session['user_id']}")

                    user="SELECT username FROM users WHERE id = %s "
                    cursor.execute(user,(session['user_id']))
                    username=cursor.fetchone()[0]
                    print(f' username: {username}')
                    # print(session["user_id"])
                return render_template('portfolio.html',username=username)
            else:
                flash("Invalid email or password",'error')
        
        except pymysql.MySQLError as e:
            print(f"Error: {e}")
            if connection:
                connection.rollback()
        
        finally:
            cursor.close()
            connection.close()
    
    return render_template('login.html')


# allow users to register and manage session
@app.route("/register", methods=['POST', 'GET'])
def register():
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
            cursor.execute(query, (username, email,hashed_password))
            connection.commit()

            cursor.close()
            connection.close()
            flash("You are registered successfully", "success")
            return render_template("portfolio.html")
        except pymysql.MySQLError as e:
            print(f"Error: {e}")
            if connection:
                connection.rollback()
            flash("An error occurred while processing your request", "danger")
            return redirect('/register')
    return render_template("register.html")

if __name__ == "__main__":
    app.run(debug=True)
