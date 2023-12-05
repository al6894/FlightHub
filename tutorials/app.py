from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'whatever_you_want'

# Handles GET form submission
@app.route('/query-example', methods=['GET'])
def query_example():
    date1 = request.args.get('date1')
    date2 = request.args.get('date2')

    # Any actual logic that you want to implement

    return render_template('query_example.html', date1=date1, date2=date2)

# Handles POST form submission
@app.route('/form-example', methods=['POST'])
def form_example():
    data1 = request.form.get('data1')
    data2 = request.form.get('data2')
    data = {
        'data1': data1,
        'data2': data2
    }

    # Any actual logic that you want to implement

    return render_template('form_example.html', data=data)

@app.route('/login', methods=['POST'])
def login():
    # Verify username and password here
    session['logged_in'] = True
    return redirect(url_for('protected'))

# Basic protected route example
@app.route('/protected', methods=['GET'])
def protected():
    if session.get('logged_in'):
        # let the user see the protected page
        return render_template('protected.html')
    else:
        # otherwise redirect to somewhere else
        return render_template('unauthorized.html')
    
from functools import wraps

# This is a decorator that will make the route only accessible to logged in users
# Make sure to import functools
def protected_route(route):
    @wraps(route)
    def wrapper(*args, **kwargs):
        if session.get('logged_in'):
            return route(*args, **kwargs) # Direct to the actual function implementation
        else:
            return render_template('unauthorized.html') # Redirect to unauthorized page or whatever of your choice
    return wrapper

# Works just like /protected, but using a decorator
@app.route('/protected2', methods=['GET'])
@protected_route
def protected2():
    return render_template('protected.html')
    
# Set the logged_in session variable to False
# The naming does not matter, whether it is logged_in or just username, it is just a key in the session dictionary
# Just make sure setting it to false or popping it from the session dictionary will let the current user not pass the protected route check anymore
@app.route('/logout')
def logout():
    session['logged_in'] = False
    return redirect(url_for('index'))

@app.route('/')
def index():
    return render_template('api_demo.html')

if __name__ == '__main__':
    app.run(debug=True)