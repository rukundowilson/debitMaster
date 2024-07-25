from flask import Flask, render_template, request, redirect, flash, session,jsonify
import pymysql
from urllib.parse import quote
import re
import bcrypt
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user
import datetime
from helpers import usd

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
            if not email:
                flash("email is required to login")
                return redirect('/login')
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
                session['user_name']= username
                print(f"Logged in as {session['user_id']}")
                print(f"Logged in as {session['user_name']}")
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


# Manage debit provision
@app.route('/debit', methods=['GET', 'POST'])
@login_required
def debit_provider():
    # assignable variables
    found_delays = 0
    has_overdue = dict()

    
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

    # calculate total paybacks daily
    timestamp = datetime.datetime.now() #contact date time every day
    year = timestamp.year
    month = timestamp.month
    day = timestamp.day
    if len(str(month)):
        month =f'0{month}'
    formated_time = f'{year}-{month}-{day}'
    print('time test',formated_time)
    get_total = " SELECT SUM(payback_amount) FROM paybacks WHERE user_id = %s AND formatted_time = %s "
    cursor.execute(get_total,(session.get('user_id'),formated_time))
    found_payback_total = cursor.fetchone()
    total_paybacks =str(found_payback_total[0])

    # find the total for expected paybacks
    expected_daily_paybacks = " SELECT SUM(amount) FROM debit WHERE user_id = %s AND payback_time_expected = %s"
    cursor.execute(expected_daily_paybacks,(session['user_id'],formated_time))
    found_expected_paybacks = cursor.fetchone()[0]

    # Find overdue payments
    get_delays = """
        SELECT SUM(amount) 
        FROM debit 
        WHERE user_id = %s 
        AND DATE(STR_TO_DATE(payback_time_expected, '%%Y-%%m-%%d')) < CURDATE()
    """
    cursor.execute(get_delays, (session['user_id'],))
    overdue_sum = cursor.fetchone()

    print("Overdue Payments Sum:", overdue_sum)
    if overdue_sum:
        found_delays = overdue_sum [0]
    print(f"found delays summed up: {found_delays}")

    overdue_number = """
        SELECT count(amount) 
        FROM debit 
        WHERE user_id = %s 
        AND DATE(STR_TO_DATE(payback_time_expected, '%%Y-%%m-%%d')) < CURDATE()
    """
    cursor.execute(overdue_number, (session['user_id']))
    number_overdue = cursor.fetchone()[0]

     # get he who has an overdue paybacks
    find_has_overdue = """
        SELECT recipient,amount
        FROM debit 
        WHERE user_id = %s 
        AND DATE(STR_TO_DATE(payback_time_expected, '%%Y-%%m-%%d')) < CURDATE()
    """
    cursor.execute(find_has_overdue, (session['user_id']))
    found_has_overdue = cursor.fetchall()
    for row in found_has_overdue:
        recipient = row[0]
        overdue_info = usd(row[1])
        if recipient not in has_overdue:
            has_overdue[recipient] = overdue_info
    print(has_overdue)
  
    if request.method == 'POST':
        recipient = request.form.get('name-to') 
        amount = request.form.get('amount')
        payback_time = request.form.get('payback') or None
        phone=request.form.get('phone')

        # web view time format
        deal_time=formated_time
        if phone:
            phone_exist = '''
                    SELECT phone_or_email FROM debit WHERE user_id = %s and phone_or_email = %s 
            '''
            cursor.execute(phone_exist,(session['user_id'],phone))
            found_phone_or_email=cursor.fetchone()
            if found_phone_or_email:
                flash("a recipient with email or phone exist in your debtors try different one or leave it null")
                return redirect('/debit')
            else:
                print("phone not familiar")
        
        if not recipient or not amount: 
            flash("All fields are required")
            return redirect("/debit")
                
        try:
            try:
                amount = float(amount)
                if amount <=0:
                    flash("you can not offer debit of amount less than one")
                    return redirect('/debit')
            except ValueError:
                flash("You must provide a number as amount")
                return redirect('/debit')
            # Insert debit record
            # Check if user with phone exists and name exist
            query_recipient = 'SELECT recipient FROM debit WHERE user_id = %s AND recipient = %s'
            cursor.execute(query_recipient, (session['user_id'], recipient))
            found_recipient = cursor.fetchone()                 
            if found_recipient:
                if phone:
                    query = '''
                        UPDATE debit SET amount = amount + %s , timestamp = %s,phone_or_email = %s WHERE user_id = %s and recipient = %s 
                    '''
                    cursor.execute(query, (amount,datetime.datetime.now(),phone,session['user_id'], recipient))
                else:
                    query = '''
                            UPDATE debit SET amount = amount + %s , timestamp = %s WHERE user_id = %s and recipient = %s
                        '''
                    cursor.execute(query, (amount,datetime.datetime.now(),session['user_id'], found_recipient[0]))
            else:
                query = '''
                    INSERT INTO debit (user_id, recipient, amount, timestamp, payback_time_expected, show_time_offerered,phone_or_email) 
                    VALUES (%s, %s, %s, %s, %s, %s,%s)
                '''
                cursor.execute(query, (session['user_id'], recipient, amount, datetime.datetime.now(), payback_time, deal_time,phone))
                
            connection.commit()
            return redirect('/dashboard')
        except pymysql.MySQLError as error:
            print(f"Error: {error}")
            flash("an error occured while processing your request")
            if connection:
                connection.rollback()
        finally:
            cursor.close()
            connection.close()

    return render_template('debit.html',
                           username=username,
                           total_debit=usd(total_debit),
                           total_paybacks = usd(total_paybacks),
                           found_expected_paybacks = usd(found_expected_paybacks),
                           found_delays = usd(found_delays),
                           number_overdue = usd(number_overdue),
                           has_overdue = has_overdue,
                           )

# show dashboard info
@app.route('/dashboard',methods=['GET'])
@login_required
def user_profile():
    # assignable variables
    has_overdue = dict()
    result_payback = {}
    # establish server connection
    connection=get_db_connection()
    cursor=connection.cursor()

    try:
        query1='SELECT username FROM users WHERE id = %s '
        cursor.execute(query1,(session['user_id']))
        username=cursor.fetchone()[0]
        
        # retrive recepient,amount and when
        get_logs='SELECT amount,recipient,show_time_offerered,id,timestamp FROM debit WHERE user_id= %s ORDER BY timestamp DESC LIMIT 6 '
        cursor.execute(get_logs,(session['user_id']))
        show_logs=cursor.fetchall()
        print(show_logs)
        paymode='debit'

        # display total debits
        get_total_debit='SELECT SUM(amount) FROM debit WHERE user_id = %s LIMIT 6 '
        cursor.execute(get_total_debit,session['user_id'])
        total_debit=cursor.fetchone()[0]
        print(total_debit)

        # provide unique id for link
        query = 'SELECT id,recipient,amount recipient FROM debit WHERE user_id = %s ORDER BY id DESC LIMIT 6 '
        cursor.execute(query,(session['user_id']))
        recipients = cursor.fetchall() 

        # calculate total paybacks daily
        timestamp = datetime.datetime.now() #contact date time every day
        year = timestamp.year
        month = timestamp.month
        day = timestamp.day
        formated_time = f'{year}-{month}-{day}'
        if len(str(month)) <10:
            month = f"0{month}"
        print('time test',formated_time)
        get_total = " SELECT SUM(payback_amount) FROM paybacks WHERE user_id = %s AND formatted_time = %s "
        cursor.execute(get_total,(session.get('user_id'),formated_time))
        found_payback_total = cursor.fetchone()
        if found_payback_total :
            total_paybacks =str(found_payback_total[0])
        else:# calculate total paybacks daily
            timestamp = datetime.datetime.now() #contact date time every day
        year = timestamp.year
        month = timestamp.month
        day = timestamp.day
        if len(str(month)) < 10:
            month = f"0{month}"
        formated_time = f'{year}-{month}-{day}'
        print('time test',formated_time)
        get_total = " SELECT SUM(payback_amount) FROM paybacks WHERE user_id = %s AND formatted_time =%s "
        cursor.execute(get_total,(session.get('user_id'),formated_time))
        found_payback_total = cursor.fetchone()
        if found_payback_total :
            total_paybacks =str(found_payback_total[0])
       
        # find the total for expected paybacks
        expected_daily_paybacks = " SELECT SUM(amount) FROM debit WHERE user_id = %s AND payback_time_expected = %s"
        cursor.execute(expected_daily_paybacks,(session['user_id'],formated_time))
        found_expected_paybacks =cursor.fetchone()[0]

        # Find overdue payments
        get_delays = """
            SELECT SUM(amount) 
            FROM debit 
            WHERE user_id = %s 
            AND DATE(STR_TO_DATE(payback_time_expected, '%%Y-%%m-%%d')) < CURDATE()
        """
        cursor.execute(get_delays, (session['user_id'],))
        overdue_sum = cursor.fetchone()

        overdue_number = """
            SELECT count(amount) 
            FROM debit 
            WHERE user_id = %s 
            AND DATE(STR_TO_DATE(payback_time_expected, '%%Y-%%m-%%d')) < CURDATE()
        """
        cursor.execute(overdue_number, (session['user_id']))
        number_overdue = cursor.fetchone()[0]

        print("Overdue Payments Sum:", overdue_sum)
        if overdue_sum:
            found_delays = overdue_sum [0]
        print(f"found delays summed up: {found_delays}")

        # get he who has an overdue paybacks
        find_has_overdue = """
            SELECT recipient,amount
            FROM debit 
            WHERE user_id = %s 
            AND DATE(STR_TO_DATE(payback_time_expected, '%%Y-%%m-%%d')) < CURDATE()
        """
        cursor.execute(find_has_overdue, (session['user_id']))
        found_has_overdue = cursor.fetchall()
        for row in found_has_overdue:
            recipient = row[0]
            overdue_info = usd(row[1])
            if recipient not in has_overdue:
                has_overdue[recipient] = overdue_info
        print(has_overdue)

        # Get recent paybacks limited to 5
        recent_paybacks = "SELECT payback_by, payback_amount FROM paybacks WHERE user_id = %s ORDER BY timestamp DESC LIMIT 5"
        cursor.execute(recent_paybacks,(session['user_id']))
        check_paybacks = cursor.fetchall()
        for i in check_paybacks:
            u_payback = i[0]
            payback_info = usd(i[1])
            if u_payback not in result_payback:
                result_payback[u_payback] = payback_info
        print("nolonger cooked",result_payback)
        print("l'm cooked",check_paybacks)


    except pymysql.MySQLError as error: 
            print(f"Error: {error}")
            flash("An error occurred while processing your request", 'danger')
            if connection:
                connection.rollback()
    finally:
        cursor.close()
        connection.close() 

    # loop through all records to retrive recepient,amount and when
    return render_template('portfolio.html',
                            username=username,
                            paymode=paymode,
                            show_logs=show_logs,
                            total_debit= usd(total_debit),
                            recipients=recipients,
                            total_paybacks = usd(total_paybacks),
                            found_expected_paybacks =usd(found_expected_paybacks),
                            found_delays = usd(found_delays),
                            number_overdue = number_overdue,
                            has_overdue = has_overdue,
                            result_payback = result_payback
                            )

# reveal recepient debit deatils
@app.route('/recipient-profile/<int:recipient_id>')
@login_required
def recipient_profile(recipient_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    
    query = 'SELECT recipient, phone_or_email, amount,timestamp,payback_time_expected FROM debit WHERE id = %s'
    cursor.execute(query, (recipient_id,))
    recipient = cursor.fetchone()

    username = session['user_name']
    
    cursor.close()
    connection.close()

    if recipient:
        return render_template('recipient.html', recipient=recipient,username = username)
    else:
        flash('Recipient not found', 'error')
        return redirect('/')

# update database for paybacks
@app.route('/payback', methods=['GET','POST'])
def payback():
    # assignable variables
    found_delays = 0
    has_overdue = dict()
    result_payback = {}

    connection = get_db_connection()
    cursor = connection.cursor()

    username = session.get('user_name')
    get_total_debit='SELECT SUM(amount) FROM debit WHERE user_id = %s LIMIT 10 '
    cursor.execute(get_total_debit,session['user_id'])
    total_debit=cursor.fetchone()[0]

    # manage notifications
    debit_settled = ''

    # calculate total paybacks daily
    timestamp = datetime.datetime.now() #contact date time every day
    year = timestamp.year
    month = timestamp.month
    day = timestamp.day
    if len(str(month)) < 10:
        month = f'0{month}'
    formated_time = f'{year}-{month}-{day}'

    # find the total for expected paybacks
    expected_daily_paybacks = " SELECT SUM(amount) FROM debit WHERE user_id = %s AND payback_time_expected = %s"
    cursor.execute(expected_daily_paybacks,(session['user_id'],formated_time))
    found_expected_paybacks = cursor.fetchone()[0]
    
    print('time test',formated_time)
    get_total = " SELECT SUM(payback_amount) FROM paybacks WHERE user_id = %s AND formatted_time = %s "
    cursor.execute(get_total,(session.get('user_id'),formated_time))
    found_payback_total = cursor.fetchone()
    if found_payback_total :
        total_paybacks =str(found_payback_total[0])
    else:
        total_paybacks = "NO PAYBACKS"

    if not username:
        flash('You must be logged in to access this page.', 'warning')
        return redirect('/login')
    
    # Find overdue payments
    get_delays = """
        SELECT SUM(amount) 
        FROM debit 
        WHERE user_id = %s 
        AND DATE(STR_TO_DATE(payback_time_expected, '%%Y-%%m-%%d')) < CURDATE()
    """
    cursor.execute(get_delays, (session['user_id'],))
    overdue_sum = cursor.fetchone()

    print("Overdue Payments Sum:", overdue_sum)
    if overdue_sum:
        found_delays = overdue_sum [0]
    print(f"found delays summed up: {found_delays}")

    overdue_number = """
        SELECT count(amount) 
        FROM debit 
        WHERE user_id = %s 
        AND DATE(STR_TO_DATE(payback_time_expected, '%%Y-%%m-%%d')) < CURDATE()
    """
    cursor.execute(overdue_number, (session['user_id']))
    number_overdue = cursor.fetchone()[0]

     # get he who has an overdue paybacks
    find_has_overdue = """
        SELECT recipient,amount
        FROM debit 
        WHERE user_id = %s 
        AND DATE(STR_TO_DATE(payback_time_expected, '%%Y-%%m-%%d')) < CURDATE()
    """
    cursor.execute(find_has_overdue, (session['user_id']))
    found_has_overdue = cursor.fetchall()
    for row in found_has_overdue:
        recipient = row[0]
        overdue_info = usd(row[1])
        if recipient not in has_overdue:
            has_overdue[recipient] = overdue_info
    print(has_overdue)

    # Get recent paybacks limited to 10
    recent_paybacks = "SELECT payback_by, payback_amount FROM paybacks WHERE user_id = %s ORDER BY timestamp DESC LIMIT 7"
    cursor.execute(recent_paybacks,(session['user_id']))
    check_paybacks = cursor.fetchall()
    for i in check_paybacks:
        u_payback = i[0]
        payback_info = usd(i[1])
        if u_payback not in result_payback:
            result_payback[u_payback] = payback_info
    print("nolonger cooked",result_payback)
    print("l'm cooked",check_paybacks)

    if request.method == 'POST':
        recipient = request.form.get('recipient')
        amount = request.form.get('amount')
    
        try:
            amount = float(amount)
            if amount == 0:
                flash("payback amount can't be 0 ")
                return redirect('/payback')
        except ValueError:
            flash ('must provide a number as amount','danger')
            return redirect('/payback')

        if recipient and amount:
            try:
                # Check if the recipient exists in the database
                get_recipient_query = "SELECT recipient, amount FROM debit WHERE user_id=%s AND recipient=%s"
                cursor.execute(get_recipient_query, (session['user_id'], recipient))
                found_recipient = cursor.fetchone()

                if found_recipient:
                    debit = found_recipient[1]
                    # check if payback amount is not greater than debit
                    if amount <= debit:
                        give_update_query = """
                            UPDATE debit 
                            SET amount = amount - %s, timestamp = %s 
                            WHERE recipient = %s AND user_id = %s
                        """
                        cursor.execute(give_update_query, (amount, datetime.datetime.now(), recipient, session['user_id']))
                        connection.commit()
                        flash('Payback successfully recorded!', 'success')

            
                        log_payback = "INSERT INTO paybacks(user_id,payback_by,payback_amount,timestamp,formatted_time) VALUES(%s,%s,%s,%s,%s)"    
                        cursor.execute(log_payback,(session['user_id'],recipient,amount,timestamp,formated_time,))
                        connection.commit()
                        # Check if any debit amount is zero and belongs to the current user
                        updated_debit = """
                            SELECT amount FROM debit WHERE user_id = %s 
                            AND recipient = %s AND amount = 0
                        """     
                        cursor.execute(updated_debit, (session["user_id"], recipient))
                        is_zero = cursor.fetchone()  # Use fetchone since we expect a single result

                        if is_zero:
                            delete_zero = """
                                DELETE FROM debit WHERE amount <= 0 AND user_id = %s AND recipient = %s
                            """ 
                            cursor.execute(delete_zero, (session['user_id'], recipient)) 
                            connection.commit()  # Commit the deletion
                            flash(f"{recipient}'s debit is settled")
                        return redirect('/dashboard')
                    else:
                        flash("payback cant be greaterthan debit",'danger')
                        return redirect('/payback')

                else:
                    flash('Recipient not found.', 'warning')
            except pymysql.MySQLError as error:
                print(f"Error: {error}")
                flash("An error occurred while processing your request", 'danger')
                if connection:
                    connection.rollback()
            finally:
                if cursor:
                    cursor.close()
                if connection:
                    connection.close()
        else:
            flash('You must provide a recipient name and payback amount.', 'warning')
            return redirect('/payback')

    return render_template('payback.html', 
                           username=username,
                           total_debit= usd(total_debit),
                           total_paybacks = usd(total_paybacks),
                           found_expected_paybacks = usd(found_expected_paybacks),
                           found_delays = usd(found_delays),
                           number_overdue = usd (number_overdue),
                           has_overdue = has_overdue,
                           result_payback = result_payback
                           )

# keep track of history
@app.route('/history',methods=['GET'])
@login_required
def history():
    username = session.get('user_name')
    # start database connection
    connection = get_db_connection()
    cursor = connection.cursor()
    # check if there is somehing before rendering
    pre_history_checkup = "SELECT * FROM paybacks WHERE user_id = %s ORDER BY id DESC"
    cursor.execute(pre_history_checkup,(session['user_id']))
    found_something=cursor.fetchall()

    check_debit = "SELECT * FROM debit WHERE user_id = %s "
    cursor.execute(check_debit,(session['user_id']))
    any_debit=cursor.fetchall()
    
    if not found_something and not any_debit:
        message = "There is no History"        
        return render_template('empty.html',message = message,username = username)
    
    print("debit logs",any_debit)
    print('all paybacks',found_something)
    return render_template('logs.html',payback_logs = found_something,debit_logs = any_debit,username = username)

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
