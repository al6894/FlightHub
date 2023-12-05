#Import Flask Library
from flask import Flask, render_template, request, session, url_for, redirect
from datetime import datetime, date, timedelta, time
from dateutil.relativedelta import relativedelta
import pymysql.cursors
from decimal import Decimal
import hashlib

#Initialize the app from Flask
app = Flask(__name__)
app.secret_key = 'some key that you will never guess'

#Configure MySQL
conn = pymysql.connect(host='localhost',
                       user='root',
                       password='',
                       db='air_ticket_reservation',
                       charset='utf8mb4',
                       cursorclass=pymysql.cursors.DictCursor)

#Hash password before storing into database
def hash_password(password):
    md5 = hashlib.md5()
    md5.update(password.encode('utf-8'))
    return md5.hexdigest()

# Searches for flights and returns flights dictionary to populate table dynamically
def search_flights(departure_date, arrival_date, departure_airport, arrival_airport):
    cursor = conn.cursor()
    query = 'SELECT * FROM flight WHERE departure_date = %s or arrival_date = %s and departure_airport = %s and arrival_airport = %s'
    cursor.execute(query, (departure_date, arrival_date, departure_airport, arrival_airport))
    flights = cursor.fetchall()
    cursor.close()

    return flights

#Get all the flights for an airline
def airline_flights(airline_name):
    cursor = conn.cursor()
    end_date = (datetime.today() + timedelta(days = 30)).date()
    query = 'SELECT * FROM flight WHERE airline_name = %s AND departure_date BETWEEN CURDATE() AND %s'
    cursor.execute(query, (airline_name, end_date))
    flights = cursor.fetchall()
    cursor.close()
    
    return flights

#Staff member can view flight ratings and comments
@app.route("/viewStats", methods = ['GET', 'POST'])
def viewStats():
    flight_num = request.args.get('flight_num')
    departure_date = request.args.get('departure_date')
    airline_name = session['airline_name']
    
    cursor = conn.cursor()
    query = 'SELECT * FROM rates WHERE airline_name = %s AND flight_num = %s AND departure_date = %s'
    cursor.execute(query, (airline_name, flight_num, departure_date))
    ratings = cursor.fetchall()
    cursor.close()
    
    avgRating = 0
    if ratings:
        for rating in ratings:
            avgRating += rating['rating']
        
        avgRating /= len(ratings)
    
    return render_template('viewStats.html', ratings=ratings, avgRating=avgRating)

# Return the top 30 most frequent customers
@app.route("/freqCustomers")
def freqCustomers(val = True):
    airline_name = session['airline_name']
    cursor = conn.cursor()
    query = 'SELECT email, f_name, l_name, COUNT(*) AS trips FROM purchases NATURAL JOIN tickets WHERE airline_name = %s and purchase_date >= %s GROUP BY email, f_name, l_name ORDER BY trips DESC LIMIT 30'
    cursor.execute(query, (airline_name, date.today() - timedelta(days=365)))
    customers = cursor.fetchall()
    cursor.close()
    
    if val:
        return render_template('customerSearch.html', customers=customers)
    else:
        return customers

# Searches for a customer within an airline
@app.route("/searchCustomer", methods = ['GET', 'POST'])
def searchCustomer():
    customers = freqCustomers(False)
    airline_name = session['airline_name']
    email = request.form.get('email')
    cursor = conn.cursor()
    query = 'SELECT * FROM purchases JOIN tickets WHERE email = %s and airline_name = %s and purchases.ticket_id = tickets.ticket_id'
    print(cursor.mogrify(query, (email, airline_name)))
    cursor.execute(query, (email, airline_name))
    flight_history = cursor.fetchall()
    
    return render_template('customerSearch.html', customers=customers, flight_history=flight_history)
    
# Dynamically updates the ticket prices based on capacity remaining
@app.route('/')
def find_tickets():
    is_signed_in = 'email' in session or 'username' in session
    #Query for information
    cursor = conn.cursor()
    query = 'SELECT * FROM flight'
    cursor.execute(query)
    flights = cursor.fetchall()
    
    for flight in flights:
        query = 'SELECT * from airplane where airline_name = %s and ID = %s'
        cursor.execute(query, (flight['airline_name'], flight['airplane_id']))
        airplane = cursor.fetchone()
        
        query = 'SELECT * from tickets where airline_name = %s and departure_date = %s and flight_num = %s'
        cursor.execute(query, (flight['airline_name'], flight['departure_date'], flight['flight_num']))
        tickets = cursor.fetchall()
        
        # update all tickets to new pricing (we are money hungry)
        if (((len(tickets)/airplane['num_seats'] * 100) < 20)):
            for ticket in tickets:
                ticket['calc_price'] = Decimal(flight['base_price'] * Decimal('1.25'))
                
    cursor.close()
    return render_template("index.html", flights=flights, is_signed_in=is_signed_in)

#Define a route to index
@app.route('/', methods = ['GET', 'POST'])
def index():
    is_signed_in = 'email' in session or 'username' in session
    if request.method == 'POST':
        departure_date = request.form.get('departure_date')
        arrival_date = request.form.get('arrival_date')
        departure_airport = request.form.get('departure_airport')
        arrival_airport = request.form.get('arrival_airport')
        
        flights = search_flights(departure_date, arrival_date, departure_airport, arrival_airport)
        
        if flights:
            return render_template("index.html", flights=flights, is_signed_in=is_signed_in)
        else:
            error = "No flights found."
            return render_template('index.html', error=error, is_signed_in=is_signed_in)
    
    return render_template('index.html', is_signed_in=is_signed_in)

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/customer_page')
def customer_page():
	return render_template('customer_page.html')

@app.route('/staff_page')
def staff_page():
	return render_template('staff_page.html')

#Authenticates the customer login
@app.route('/customerloginAuth', methods=['GET', 'POST'])
def customerloginAuth():
    email = request.form.get('email')
    password = request.form.get('password')
    
    if password is None:
        error = "Password is required."
        return render_template('customer_page.html', error=error)
    
    hashed_password = hash_password(password)

    cursor = conn.cursor()
    query = 'SELECT * FROM customer WHERE email = %s and password = %s'
    cursor.execute(query, (email, hashed_password))
    data = cursor.fetchone()
    cursor.close()
    error = None
    
    if(data):
        session['email'] = email
        session['password'] = hashed_password
        is_signed_in = 'email' in session
        return render_template('index.html', is_signed_in=is_signed_in)
    else:
        error = 'Invalid login or email'
        return render_template('customer_page.html', error=error)

#Authenticates customer register
@app.route('/customerAuth', methods=['GET', 'POST'])
def customerAuth():
    is_signed_in = 'email' in session
    email = request.form['email']
    password = request.form['password']
    f_name = request.form['firstname']
    l_name = request.form['lastname']
    building_name = request.form['building']
    street_name = request.form['street']
    apt_num = request.form['apartment']
    city = request.form['city']
    state = request.form['state']
    zip_code = request.form['zipcode']
    passport_num = request.form['passport number']
    passport_exp = request.form['expiration date']
    passport_country = request.form['passport country']
    DOB = request.form['DOB']
    
    cursor = conn.cursor()
    query = 'SELECT * FROM customer WHERE email = %s'
    cursor.execute(query, (email))
    data = cursor.fetchone()
    error = None
    
    hashed_password = hash_password(password)
    
    if(data):
        #If the previous query returns data, then customer exists
        error = "This customer already exists"
        return render_template('customer_page.html', error = error)
    else:
        ins = 'INSERT INTO customer VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'
        cursor.execute(ins, (email, f_name, l_name, hashed_password, building_name, street_name, apt_num, city, state, zip_code, 
                             passport_num, datetime.strptime(passport_exp, '%Y-%m-%d').date(), 
                             passport_country, datetime.strptime(DOB, '%Y-%m-%d').date()))
        conn.commit()
        cursor.close()
        return render_template('index.html', is_signed_in=is_signed_in)
    
#Authenticates the register
@app.route('/staffAuth', methods=['GET', 'POST'])
def staffAuth():
    is_signed_in = 'username' in session
    airline_name = request.form['airline_name']
    username = request.form['username']
    f_name = request.form['f_name']
    l_name = request.form['l_name']
    password = request.form['password']
    DOB = request.form['DOB']
    
    cursor = conn.cursor()
    query = 'SELECT * FROM airline_staff WHERE airline_name = %s and username = %s'
    cursor.execute(query, (airline_name, username))
    data = cursor.fetchone()
    error = None
    
    hashed_password = hash_password(password)
    
    if(data):
        #If the previous query returns data, then staff member exists
        error = "This airline staff already has an account."
        return render_template('staff_page.html', error = error)
    else:
        ins = 'INSERT INTO airline_staff VALUES(%s, %s, %s, %s, %s, %s)'
        cursor.execute(ins, (airline_name, username, f_name, l_name, hashed_password, datetime.strptime(DOB, '%Y-%m-%d').date()))
        conn.commit()
        cursor.close()
        return render_template('index.html', is_signed_in=is_signed_in)

#Authenticates the staff login
@app.route('/staffloginAuth', methods=['GET', 'POST'])
def staffloginAuth():
    airline_name = request.form['airline_name']
    username = request.form['username']
    password = request.form['password']
    
    if password is None:
        error = "Password is required."
        return render_template("staff_page.html")
    
    hashed_password = hash_password(password)
    
    cursor = conn.cursor()
    query = 'SELECT * FROM airline_staff WHERE airline_name = %s and username = %s and password = %s'
    cursor.execute(query, (airline_name, username, hashed_password))
    data = cursor.fetchone()
    cursor.close()
    error = None
    
    
    if(data):
        session['airline_name'] = airline_name
        session['username'] = username
        session['password'] = password
        is_signed_in = 'username' in session
        return render_template('index.html', is_signed_in=is_signed_in)
    else:
        error = 'Account with these credentials does not exist'
        return render_template('staff_page.html', error=error)
    
@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        flights = airline_flights(session['airline_name'])
        revenue = viewRevenue(session['airline_name'])
        return render_template('staffdashboard.html', flights=flights, revenue=revenue)
    elif 'email' in session:
        purchases = purchaseHistory(session['email'])
        expenses = getExpenses(session['email'])
        return render_template('clientdashboard.html', purchases=purchases, expenses=expenses)

@app.route('/addAirport', methods = ['POST'])
def addAirport():
    airport_code = request.form['airport_code']
    airport_name = request.form['airport_name']
    city = request.form['city']
    country = request.form['country']
    num_terminals = request.form['num_terminals']
    airport_type = request.form['airport_type']
    
    cursor = conn.cursor()
    query = 'SELECT * FROM airport WHERE airport_code = %s'
    cursor.execute(query, (airport_code))
    data = cursor.fetchone()
    error = None
    if(data):
        #If the previous query returns data, then airport exists
        error = "Airport already exists."
        return dashboard(error)
    else:
        ins = 'INSERT INTO airport VALUES(%s, %s, %s, %s, %s, %s)'
        cursor.execute(ins, (airport_code, airport_name, city, country, num_terminals, airport_type))
        conn.commit()
        cursor.close()
        return dashboard()

# Add airplane (works)
@app.route('/addAirplane', methods = ['POST'])
def addAirplane():
    # By default, airline name is the same as the staff member's
    # cannot add airplanes for other airlines.
    airline_name = session['airline_name']
    ID = request.form['ID']
    num_seats = request.form['num_seats']
    manufacturer = request.form['manufacturer']
    model_num = request.form['model_num']
    manufactured_date = request.form['manufactured_date']
    manufactured_date = datetime.strptime(manufactured_date, '%Y-%m-%d').date()
    # Automatically calculate difference from today and manufactured date.
    date_difference = relativedelta(datetime.today().date(), manufactured_date)
    age = date_difference.years + date_difference.days/365
    
    cursor = conn.cursor()
    query = 'SELECT * FROM airplane WHERE airline_name = %s and ID = %s'
    cursor.execute(query, (airline_name, ID))
    data = cursor.fetchone()
    error = None
    
    if(data):
        error = "Airplane already exists."
        return dashboard(error)
    else:
        ins = 'INSERT INTO airplane VALUES(%s, %s, %s, %s, %s, %s, %s)'
        cursor.execute(ins, (airline_name, ID, num_seats, manufacturer, model_num, 
                             manufactured_date, age))
        conn.commit()
        cursor.close()
        return dashboard()

# Creates a flight (works)
@app.route('/createFlight', methods = ['GET', 'POST'])
def createFlight():
    # By default, airline name is the same as the staff member's
    # cannot create flights for other airlines.
    airline_name = session['airline_name']
    flight_num = request.form['flight_num']
    departure_date = request.form['departure_date']
    departure_time = request.form['departure_time']
    arrival_date = request.form['arrival_date']
    arrival_time = request.form['arrival_time']
    base_price = request.form['base_price']
    departure_airport = request.form['departure_airport']
    arrival_airport = request.form['arrival_airport']
    airplane_airline = request.form['airplane_airline']
    airplane_id = request.form['airplane_id']
    status = request.form['status']
    
    cursor = conn.cursor()
    query = 'SELECT * FROM flight WHERE airline_name = %s and departure_date = %s and flight_num = %s'
    cursor.execute(query, (airline_name, departure_date, flight_num))
    data = cursor.fetchone()
    error = None
    if(data):
        #If the previous query returns data, then flight exists
        error = "A flight with these credentials already exists."
        return dashboard(error)
    else:
        ins = 'INSERT INTO flight VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'
        cursor.execute(ins, (airline_name, flight_num, datetime.strptime(departure_date,'%Y-%m-%d'), departure_time, 
                             datetime.strptime(arrival_date,'%Y-%m-%d'), arrival_time, base_price, departure_airport, arrival_airport,
                             airplane_airline, airplane_id, status))
        conn.commit()
        cursor.close()
        return dashboard()

# Change flight status (works)
@app.route('/changeStatus', methods = ['GET', 'POST'])
def changeStatus():
    # By default, airline name is the same as the staff member's
    # cannot change status for other airlines.
    airline_name = session['airline_name']
    flight_num = request.form['flight_num']
    departure_date = request.form['departure_date']
    status = request.form['status']
    
    cursor = conn.cursor()
    query = 'SELECT * FROM flight WHERE airline_name = %s and flight_num = %s and departure_date = %s'
    cursor.execute(query, (airline_name, flight_num, departure_date))
    data = cursor.fetchone()
    error = None
    
    if not data:
        error = "Flight does not exist."
        return dashboard(error)
    else:
        update = 'UPDATE flight SET status = %s WHERE airline_name = %s and flight_num = %s and departure_date = %s'
        cursor.execute(update, (status, airline_name, flight_num, departure_date))
        conn.commit()
        cursor.close()
        return dashboard()

# Schedules maintenance (works)
@app.route('/maintenance', methods = ['POST'])
def maintenance():
    # By default, airline name is the same as the staff member's
    # cannot schedule maintenance for other airlines.
    airline_name = session['airplane_airline']
    ID = request.form['airplane_id']
    start_date = request.form['start_date']
    start_time = request.form['start_time']
    end_date = request.form['end_date']
    end_time = request.form['end_time']
    
    cursor = conn.cursor()
    query = 'SELECT * FROM airplane WHERE airline_name = %s and ID = %s'
    cursor.execute(query, (airline_name, ID))
    data = cursor.fetchone()
    error = None
    if not data:
        error = "Plane does not exist."
        return dashboard(error)
    else:
        ins = 'INSERT INTO maintenance VALUES(%s, %s, %s, %s, %s, %s)'
        cursor.execute(ins, (airline_name, ID, datetime.strptime(start_date,'%Y-%m-%d').date(), start_time, 
                             datetime.strptime(end_date,'%Y-%m-%d').date(), end_time))
        conn.commit()
        cursor.close()
        return dashboard()
    
@app.route('/dashboard', methods = ['GET'])
def viewRevenue(airline_name):
    cursor = conn.cursor()
    query = 'SELECT sum(calc_price) as revenue FROM purchases JOIN tickets WHERE airline_name = %s and purchases.ticket_id = tickets.ticket_id'
    cursor.execute(query, (airline_name))
    revenue = cursor.fetchone()
    
    return revenue
    
@app.route('/customerFlights', methods = ['GET'])
def customerFlights():
    cursor = conn.cursor()
    query = 'SELECT * FROM purchases WHERE email = %s'
    cursor.execute(query,(session['email']))
    purchases = cursor.fetchall()
    
    return dashboard()
    

# Checks if customer is logged in before letting them buy ticket
@app.route('/buy-tickets', methods = ['GET', 'POST'])
def buy_tickets_route():
    if 'email' in session:
        airline_name = request.args.get('airline_name')
        flight_num = request.args.get('flight_num')
        departure_date = request.args.get('departure_date')
        airplane_id = request.args.get('airplane_id')
        f_name = request.form.get('f_name')
        l_name = request.form.get('l_name')
        DOB = request.form.get('DOB')
        card_type = request.form.get('card_type')
        card_num = request.form.get('card_num')
        card_name = request.form.get('card_name')
        exp_date = request.form.get('exp_date')

        # Store hidden values in the session
        session['flight_details'] = {
            'airline_name': airline_name,
            'flight_num': flight_num,
            'departure_date': departure_date,
            'airplane_id': airplane_id,
        }
        
        buy_tickets(f_name, l_name, DOB, card_type, card_num, card_name, exp_date)
        return dashboard()
    else:
        error = "Users must be signed-in to buy tickets."
        return dashboard(error)

#Protected function
def buy_tickets(f_name, l_name, DOB, card_type, card_num, card_name, exp_date):
    is_signed_in = 'email' in session or 'username' in session
    #Implement ticket buying logic here
    if request.method == 'POST':
        email = session['email']
        flight_details = session['flight_details']
        purchase_date = date.today()
        purchase_time = datetime.today().time()
        
        cursor = conn.cursor()
        #Sell a ticket only if it has not been sold already.
        query = 'SELECT * FROM tickets WHERE airline_name = %s and departure_date = %s and flight_num = %s AND NOT EXISTS (SELECT 1 FROM purchases where purchases.ticket_id = tickets.ticket_id)'
        cursor.execute(query, (flight_details['airline_name'], flight_details['departure_date'], flight_details['flight_num']))
        ticket = cursor.fetchone()
        error = None
        
        if not ticket:
            error = "No tickets left for this flight."
            return render_template('index.html', is_signed_in=is_signed_in, error = error)
        else:
            ticket_id = ticket['ticket_id']
            ins = 'INSERT INTO purchases VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'
            cursor.execute(ins, (email, ticket_id, f_name, l_name, datetime.strptime(DOB,'%Y-%m-%d').date(), card_type, 
                                card_num, card_name, datetime.strptime(exp_date,'%Y-%m-%d').date(), purchase_date, purchase_time))
            conn.commit()
            cursor.close()
            
        error = "Tickets purchased successfully!"
        return dashboard(error)

# Checks if customer is logged in before letting them rate
@app.route('/rates', methods = ['GET', 'POST'])
def rates_route():
    if 'email' in session:
        airline_name = request.args.get('airline_name')
        flight_num = request.args.get('flight_num')
        departure_date = request.args.get('departure_date')
        rating = request.form.get('rating')
        comment = request.form.get('comment')

        rates(airline_name, flight_num, departure_date, rating, comment)
        return render_template('rates.html', rating=rating, comment=comment)
    else:
        error = "Users must be signed-in to rate flights."
        return render_template('customer_page.html', error = error)

# Protected function
def rates(airline_name, flight_num, departure_date, rating, comment):  
    is_signed_in = 'email' in session or 'username' in session
    cursor = conn.cursor()
    # Should only be able to rate past flights
    query = 'SELECT distinct * FROM purchases natural join tickets WHERE email = %s and departure_date >= %s or departure_date <= %s'
    cursor.execute(query, (session['email'], datetime.today().date(), datetime.today().date()))
    previous_flights = cursor.fetchall()
    error = None
        
    if not previous_flights:
        error = "No flights taken."
        return render_template('index.html', is_signed_in=is_signed_in, error = error)
    else:
        ins = 'INSERT INTO rates VALUES(%s, %s, %s, %s, %s, %s)'
        cursor.execute(ins, (session['email'], airline_name, flight_num, departure_date, comment, rating))
        conn.commit()
        cursor.close()
        
    return render_template('rates.html')

# Get purchase history of a customer
def purchaseHistory(email):
    currentDate = datetime.today().date()

    cursor = conn.cursor()
    query = 'SELECT * FROM purchases NATURAL JOIN tickets WHERE email = %s and departure_date >= %s or departure_date <= %s'
    print(cursor.mogrify(query, (email, currentDate, currentDate)))
    cursor.execute(query, (email, currentDate, currentDate))
    purchases = cursor.fetchall()
    cursor.close()

    return purchases

@app.route('/cancel', methods=['POST'])
def cancelFlight():
    if 'email' in session:
        cursor = conn.cursor()
        email = session['email']
        # Fetch ticket information including departure date and time
        query = "SELECT DISTINCT purchases.ticket_id AS purchase_ticket_id, flight.departure_date, flight.departure_time FROM purchases JOIN tickets JOIN flight WHERE email = %s and purchases.ticket_id = tickets.ticket_id and tickets.flight_num = flight.flight_num"
        print(cursor.mogrify(query, (email)))
        cursor.execute(query, (email))
        ticket = cursor.fetchone()
        error = None
        

        if ticket:
            # Extract departure date and time from the result
            departure_date = ticket['departure_date']
            departure_time = ticket['departure_time']
            
            # Combine departure date and time into a datetime object
            departure_datetime = datetime.combine(departure_date, time()) + departure_time

            # Calculate the difference between current datetime and departure datetime
            time_difference = datetime.now() - departure_datetime
            print(time_difference)

            # Check if the flight is more than 24 hours away
            if time_difference > timedelta(hours=24):
                # Perform cancellation
                delete_query = "DELETE FROM purchases WHERE email = %s and ticket_id = %s"
                cursor.execute(delete_query, (email, ticket['purchase_ticket_id']))
                cursor.close()
                conn.commit()
                purchases = purchaseHistory(email)
                expenses = getExpenses(email)
                return render_template("clientdashboard.html", purchases=purchases, expenses=expenses)
            else:
                purchases = purchaseHistory(email)
                expenses = getExpenses(email)
                error = "Cannot cancel within 24 hours of departure"
                return render_template("clientdashboard.html", purchases=purchases, expenses=expenses, error=error)
        else:
            error = "Ticket does not exist."
            return dashboard(error)

@app.route('/getExpenses')
def getExpenses_route():
    return dashboard()
    
#Protected: Calculate total expenses of a customer
def getExpenses(email): 
    cursor = conn.cursor()
    query = 'SELECT distinct * FROM purchases JOIN tickets WHERE email = %s and purchases.ticket_id = tickets.ticket_id'
    cursor.execute(query, (email))
    purchases = cursor.fetchall()
    cursor.close()
        
    if not purchases:
        return 0
    else:
        expenses = 0
        for purchase in purchases:
            expenses += float(purchase['calc_price'])
        expenses = round(expenses, 2)
    
    return expenses
    

@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')
		
if __name__ == "__main__":
	app.run('127.0.0.1', 5000, debug = True)